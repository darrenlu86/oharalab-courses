"""
crawlers/common.py — 三支爬蟲（股價／新聞／供應鏈）共用的工具函式。

做什麼：
    集中放「跟抓哪個網站無關、每支爬蟲都要做」的事：
    - robots.txt 檢查（尊重網站方的爬取規則）
    - 統一的 User-Agent（讓對方看得出來源與聯絡方式）
    - rate limit（節流，避免造成對方伺服器負擔）
    - 失敗重試（exponential backoff）
    - logging 設定（同時輸出到終端機與檔案）

為什麼這樣設計：
    三支爬蟲抓的網站型態完全不同（官方 JSON API／React SPA／
    server-rendered HTML），但「怎麼當一個有禮貌、有韌性的爬蟲」這件事是
    共通的，抽出來一份，三支爬蟲各自 import 使用，不重複寫三次同樣的重試
    與節流邏輯（DRY：Don't Repeat Yourself）。
"""

from __future__ import annotations

import logging
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

import requests

# User-Agent：依規格書 §5 固定字串。附上聯絡方式，是爬蟲禮儀的基本功——
# 讓對方網站管理員看到異常流量時，知道是誰、可以怎麼聯絡。
USER_AGENT = (
    "tsmc-analysis-edu-crawler/1.0 (educational project; contact: kevin868686@gmail.com)"
)

# 各爬蟲的 rate limit（單位：秒）。三支爬蟲抓的網站負擔能力不同，
# 分開命名方便之後個別調整，不用共用一個數字互相牽制。
RATE_LIMIT_STOCK = 3
RATE_LIMIT_NEWS = 2
RATE_LIMIT_SUPPLY_CHAIN = 2

# 重試的 exponential backoff 秒數：第一次失敗等 2 秒重試、
# 第二次失敗等 4 秒、第三次失敗等 8 秒，共重試 3 次（加上最初那次共 4 次嘗試）。
RETRY_BACKOFF_SECONDS = [2, 4, 8]

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "crawler.log"


def setup_logging(name: str) -> logging.Logger:
    """設定並回傳一個同時輸出到 stdout 與 logs/crawler.log 的 logger。

    做什麼＋為什麼：
        爬蟲不能用 print() 除錯——print 訊息無法分等級、關掉終端機就消失。
        正式的 logging 模組可以「同一則訊息」同時送到終端機（方便當下觀察）
        與檔案（方便事後排查「哪一天哪一筆資料抓失敗」），還能標示等級
        （INFO/WARNING/ERROR）。

    注意：
        重複呼叫本函式（例如同一支爬蟲的多個函式都呼叫一次）不會疊加
        handler——用 `if logger.handlers` 先檢查是否已經設定過，避免同一則
        訊息被印兩次、三次。
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # 已經設定過，直接回傳既有的 logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# 供 check_robots_allowed() 在「robots.txt 抓取失敗、退回預設允許」時記 log
# 用——這個情境橫跨三支爬蟲共用，直接複用 setup_logging() 寫進同一份
# logs/crawler.log，呼叫端不需要（也不必）自己重複判斷這件事。
_robots_logger = setup_logging("crawlers.common")


def check_robots_allowed(url: str, user_agent: str = USER_AGENT) -> bool:
    """檢查目標網址是否允許本爬蟲的 User-Agent 抓取（依 robots.txt 規則）。

    做什麼＋為什麼：
        用標準庫 urllib.robotparser 讀取目標網站的 /robots.txt，判斷指定
        路徑是否允許被抓取。這是爬蟲禮儀的第一步——尊重網站方透過
        robots.txt 表達的意願，禁止的路徑一律跳過，不強行抓取。

    回傳值語意（初學者常見誤解）：
        True 有兩種可能：(1) robots.txt 明確允許，或 (2) robots.txt 本身
        抓取失敗（網路錯誤、伺服器沒有這個檔案等）——這裡選擇保守地視為
        「允許」，因為抓不到規則不等於對方明確禁止，這是刻意的教學取捨，
        不是邏輯漏洞。兩種情況呼叫端拿到的都是同一個 True，光看回傳值
        分不出來，所以本函式在情況 (2) 會自己記一筆 WARNING log（不需要
        呼叫端額外處理），事後排查時可以從 log 檔分辨這次的 True 是真的
        允許、還是抓取失敗退回的預設值。
    """
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception as exc:
        _robots_logger.warning(
            "robots.txt 抓取失敗，依教學取捨視為允許抓取（詳見本函式 docstring）："
            "%s（錯誤：%s）",
            robots_url,
            exc,
        )
        return True
    return rp.can_fetch(user_agent, url)


def polite_get(
    url: str,
    logger: logging.Logger,
    rate_limit_seconds: float,
    **requests_kwargs,
) -> requests.Response | None:
    """帶 rate limit 與重試機制（exponential backoff）的 GET 請求。

    做什麼：
        1. 送出前先 sleep `rate_limit_seconds` 秒——每次請求前都會等待，
           確保連續呼叫時兩次請求間隔一定不小於這個秒數。
        2. 失敗（連線錯誤、逾時、HTTP 4xx/5xx）就用 2s / 4s / 8s 的
           exponential backoff 依序重試，最多重試 3 次。
        3. 全部重試完仍失敗，記一筆 ERROR log 並回傳 None，由呼叫端決定
           要不要跳過這筆繼續處理下一筆——單筆失敗絕不能讓整支爬蟲中斷
           （§9 品質底線）。

    參數：
        url: 目標網址。
        logger: 由 setup_logging() 建立的 logger。
        rate_limit_seconds: 這次請求前要 sleep 幾秒。
        **requests_kwargs: 透傳給 requests.get() 的參數（如 params）。

    注意：
        呼叫端拿到 None 時務必檢查，不要假設一定拿得到 Response——
        這是本函式刻意用回傳值（而不是拋例外）表達「這筆先跳過」的設計。

    注意（SSL 驗證失敗會提早結束重試，不會走完整套 backoff）：
        TLS/SSL 驗證失敗（requests.exceptions.SSLError）跟逾時／連線中斷
        不一樣——同一個憑證鏈重試幾次，結果都是一樣的失敗，不像逾時可能
        只是暫時性的網路壅塞。因此第一次遇到 SSLError 就會直接記一筆
        WARNING log、跳出重試迴圈，不會傻傻等完 2s/4s/8s 共 14 秒的
        backoff 才回報失敗——這是本專案實際遇到 ic.tpex.org.tw 憑證鏈問題
        後加的最佳化（詳見 crawlers/supply_chain_crawler.py 模組 docstring），
        但寫在這裡是因為所有用 polite_get() 的爬蟲都適用同一個道理，不只
        supply_chain 這一支。
    """
    headers = requests_kwargs.pop("headers", {})
    headers.setdefault("User-Agent", USER_AGENT)

    last_error: Exception | None = None
    # attempts = [0] + backoff 秒數清單：index 0 是「第一次嘗試」（不用等待），
    # 之後每個元素是失敗後要等多久才重試。
    attempts = [0, *RETRY_BACKOFF_SECONDS]

    for retry_index, backoff in enumerate(attempts):
        if backoff:
            logger.warning(
                "請求失敗，%d 秒後進行第 %d 次重試：%s", backoff, retry_index, url
            )
            time.sleep(backoff)

        time.sleep(rate_limit_seconds)

        try:
            response = requests.get(
                url, headers=headers, timeout=10, **requests_kwargs
            )
            response.raise_for_status()
            return response
        except requests.exceptions.SSLError as exc:
            # 注意：SSLError 是 RequestException 的子類別，這個 except 子句
            # 必須寫在下面那個更廣泛的 except requests.RequestException
            # 之前，Python 才會用這個較精確的分支處理它（except 是照順序
            # 比對，不是自動挑最精確的那個）。
            last_error = exc
            logger.warning(
                "TLS/SSL 驗證失敗（通常是憑證鏈相容性問題，不是網路不穩定），"
                "已提早結束重試、不再等待剩餘的 backoff：%s（錯誤：%s）",
                url,
                exc,
            )
            break  # 同一憑證鏈重試結果不會變，繼續 backoff 只是白等最多 14 秒
        except requests.RequestException as exc:
            last_error = exc
            continue

    logger.error(
        "請求最終失敗（已重試 %d 次），跳過：%s（錯誤：%s）",
        len(RETRY_BACKOFF_SECONDS),
        url,
        last_error,
    )
    return None
