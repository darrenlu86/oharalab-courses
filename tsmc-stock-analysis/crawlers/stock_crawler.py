"""
crawlers/stock_crawler.py — 股價爬蟲：抓取台積電（2330）每日股價（TWSE 官方 API）。

做什麼：
    呼叫證交所（TWSE）官方 JSON API，逐月抓取指定股票的每日收盤資訊，
    清理成統一格式後透過 db.factory.get_repository() 寫入資料庫。

為什麼這樣設計（有官方 API 就不爬網頁）：
    TWSE 本身就提供公開、穩定的 JSON 端點回傳每日股價，不需要用瀏覽器
    模擬或解析 HTML 表格——能用官方 API 就優先用，理由：
    1. 穩定：官方端點的資料格式不會像網頁排版一樣說改就改。
    2. 合法／有禮貌：這是 TWSE 主動開放的資料介面，不是繞過限制硬爬。
    3. 省資源：一次 API 呼叫換整月資料（約 20 個交易日），
       遠比逐頁爬網頁划算——這也是本專案「新聞」「上下游」兩支爬蟲
       都要真的用 Playwright / requests+bs4 去解析頁面，唯獨股價這支
       不用的原因。

流程（設計規格書 §5a）：
    1. checkpoint：呼叫 repo.get_latest_price_date() 拿目前資料庫裡
       最新的交易日期，決定要從哪個月開始抓——這是「增量爬取」的核心，
       避免每次執行都重頭全抓一遍。
    2. 完全沒有資料時（第一次執行），從「今天所在月份」往前推
       N 個月開始 backfill（N 由 CLI 參數 --months 指定，預設 3）。
    3. 逐月呼叫 API，一路抓到本月為止。
    4. 每月的原始 JSON 資料逐列清理（民國年轉西元、千分位轉數字、
       漲跌價差的正負號與特殊符號），組成 upsert_daily_prices()
       需要的 dict 格式。
    5. 呼叫 repo.upsert_daily_prices() 寫入——因為是以
       (stock_symbol, trade_date) 為唯一鍵 upsert，即使 checkpoint
       落在月中、重抓了同一個月，也只會覆寫同樣的值，不會產生
       重複列，天然具備冪等性（重跑結果不變）。

注意：
    本檔案的「清理函式」（convert_roc_date、parse_number、parse_change、
    clean_daily_row）刻意寫成純函式（輸入字串 → 輸出乾淨的值，完全不做
    任何網路或資料庫 I/O），這樣可以完全不連網路、不碰資料庫就對它們
    寫單元測試（見 tests/test_stock_crawler.py），也比較容易個別驗證
    每一種奇怪的輸入格式。
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

# 讓本檔案不論用 `python -m crawlers.stock_crawler`（建議方式，會自動把
# 目前工作目錄加進 sys.path）還是直接 `python crawlers/stock_crawler.py`
# 執行，都能正確 import 到專案根目錄的 config / db 套件。
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.common import (  # noqa: E402
    RATE_LIMIT_STOCK,
    check_robots_allowed,
    polite_get,
    setup_logging,
)
from db.factory import get_repository  # noqa: E402

TWSE_STOCK_DAY_URL = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
DEFAULT_MONTHS = 3
DEFAULT_STOCK_SYMBOL = "2330"

logger = setup_logging("stock_crawler")


# =====================================================================
# 清理純函式（輸入 → 輸出，不做 I/O，方便單元測試）
# =====================================================================


def convert_roc_date(roc_date: str | None) -> str | None:
    """民國年日期字串轉西元 ISO 日期。

    例："115/07/01" -> "2026-07-01"（西元年 = 民國年 + 1911）。

    為什麼：TWSE API 回傳的日期一律用民國年，資料庫與 dashboard 統一用
    西元 ISO8601（YYYY-MM-DD）比較好排序、比較，也跟新聞爬蟲的
    published_at 格式一致。

    注意（禁止捏造資料）：格式不符（缺斜線、年份不是數字、月份不在
    1-12、日期不在 1-31 等）一律回傳 None，呼叫端要記 log 跳過這一列，
    不可以硬猜一個日期出來。

    注意（範圍檢查是「粗略」檢查，不是完整曆法驗證）：
        這裡只檢查 month 落在 1-12、day 落在 1-31，不會檢查「這個月實際上
        有沒有這麼多天」——例如 "115/02/30"（2 月 30 日，根本不存在）會
        通過這裡的檢查，被轉成一個格式正確但曆法上不存在的日期字串。真的
        要做完整曆法驗證應該改用 datetime.date(...) 建構子（遇到不存在的
        日期會拋 ValueError），但那樣要多 import 一個模組、多寫一層
        try/except，對這個純函式來說是不成比例的複雜度。這裡的範圍檢查
        目的是擋掉「明顯不合理」的髒資料（例如月份 13、日期 99 這種一看
        就知道是解析錯位或欄位對錯的情況），不是要取代完整曆法正確性
        驗證——資料源是 TWSE 官方 API，正常情況下不會出現真正的不存在
        日期，這個取捨在教學專案的脈絡下是合理的。
    """
    if not roc_date:
        return None
    parts = roc_date.strip().split("/")
    if len(parts) != 3:
        return None
    roc_year_str, month_str, day_str = parts
    try:
        roc_year = int(roc_year_str)
        month = int(month_str)
        day = int(day_str)
    except ValueError:
        return None
    if not (1 <= month <= 12):
        return None
    if not (1 <= day <= 31):
        return None
    western_year = roc_year + 1911
    return f"{western_year:04d}-{month:02d}-{day:02d}"


def parse_number(raw: str | None) -> float | None:
    """把 TWSE 常見的「千分位逗號數字」字串轉成 float；無法解析回傳 None。

    例："37,544,470" -> 37544470.0、"2,495.00" -> 2495.0、
        "--" / "" -> None（TWSE 用 "--" 表示當天沒有這個數值）。

    注意：這裡統一回傳 float；volume/turnover/transactions 這些
    「概念上是整數」的欄位，由 parse_int() 在這基礎上再轉一次 int——
    parse_number() 本身只負責「拿掉千分位逗號、判斷是不是缺值」這件事，
    保持單一職責，方便個別測試。
    """
    if raw is None:
        return None
    text = raw.strip()
    if text in ("", "--"):
        return None
    text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(raw: str | None) -> int | None:
    """把千分位數字字串轉成 int（給 volume / turnover / transactions 用）。"""
    value = parse_number(raw)
    if value is None:
        return None
    return int(value)


def parse_change(raw: str | None) -> float | None:
    """解析「漲跌價差」欄位，處理 TWSE 特有的正負號與 X 前綴。

    已實測觀察到的格式（2026-07-23 對 TWSE API 17 個月份、上百筆真實
    資料的實測結果，詳見任務驗收證據）：
        "+95.00" -> 95.0（上漲 95 元）
        "-40.00" -> -40.0（下跌 40 元）
        "X0.00"  -> 0.0（除權息等基準價調整日；TWSE 官方資料在這種
                    情況一律寫成 "X0.00"，實測 17 個月份、4 筆 X 開頭的
                    資料全部都是 "X0.00"，沒有出現過 "X15.00" 這種
                    非零情形，因此如實反映成 0.0，不臆測其他數值）
        "--" / "" -> None（沒有比較基準可用）

    注意：這是根據「實測決定」而非憑空假設——規格書 §5a 明講「X 開頭
    視為 0 或 None，實測決定」，本函式的分支就是那次實測的結論。
    """
    if raw is None:
        return None
    text = raw.strip()
    if text in ("", "--"):
        return None

    sign = 1
    if text.startswith("+"):
        text = text[1:]
    elif text.startswith("-"):
        sign = -1
        text = text[1:]
    elif text.upper().startswith("X"):
        text = text[1:]
        # 注意：X 開頭實測皆為 "X0.00"，數值本身就是 0，正負號不影響結果。

    try:
        return sign * float(text.replace(",", ""))
    except ValueError:
        return None


def clean_daily_row(stock_symbol: str, raw_row: list[str]) -> dict | None:
    """把 TWSE API 單列原始資料清理成 upsert_daily_prices() 要的 dict 格式。

    TWSE 回傳的 fields 順序固定為（已於任務驗收時實測確認）：
        日期, 成交股數, 成交金額, 開盤價, 最高價, 最低價, 收盤價,
        漲跌價差, 成交筆數, 註記

    做什麼：依序取出對應欄位、呼叫上面的純函式清理，組成一筆 dict。

    注意（禁止捏造資料）：日期或任一價格／成交量／成交筆數欄位解析
    失敗（回傳 None）時，整列直接回傳 None，由呼叫端記 log 跳過——
    寧可缺這一天的資料，也不要用 0 或前一筆的值頂替，塞一筆錯的資料
    進資料庫。"漲跌價差"（change）是唯一的例外：它本身就可能合法地
    沒有值（例如當天沒有比較基準），None 對這個欄位是有效的清理結果，
    不會導致整列被丟棄。
    """
    if len(raw_row) < 9:
        logger.warning("股價資料欄位數不足（預期至少 9 欄），跳過：%s", raw_row)
        return None

    trade_date = convert_roc_date(raw_row[0])
    volume = parse_int(raw_row[1])
    turnover = parse_int(raw_row[2])
    open_price = parse_number(raw_row[3])
    high_price = parse_number(raw_row[4])
    low_price = parse_number(raw_row[5])
    close_price = parse_number(raw_row[6])
    change = parse_change(raw_row[7])
    transactions = parse_int(raw_row[8])

    required_fields = {
        "trade_date": trade_date,
        "volume": volume,
        "turnover": turnover,
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "transactions": transactions,
    }
    missing = [name for name, value in required_fields.items() if value is None]
    if missing:
        logger.warning("必要欄位解析失敗 %s，跳過這一列：%s", missing, raw_row)
        return None

    return {
        "stock_symbol": stock_symbol,
        "trade_date": trade_date,
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "volume": volume,
        "turnover": turnover,
        "transactions": transactions,
        "change": change,
    }


# =====================================================================
# 月份計算（純函式，不做 I/O）
# =====================================================================


def month_start(d: date) -> date:
    """回傳某日期所在月份的第一天。"""
    return d.replace(day=1)


def add_months(d: date, delta: int) -> date:
    """回傳 d 往前（delta 為負）或往後（delta 為正）delta 個月的第一天。

    注意：只處理「月份第一天」的加減，不處理任意日期加月份可能遇到的
    「目標月沒有這麼多天」問題（例如 1/31 加一個月），因為本檔案呼叫
    這個函式時 d 一定已經是 month_start() 過的第一天。
    """
    month_index = d.month - 1 + delta
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def determine_start_month(
    latest_trade_date: str | None, months: int, today: date
) -> date:
    """依 checkpoint 決定要從哪個月開始抓。

    做什麼＋為什麼：
        - 完全沒有資料（latest_trade_date is None）：從「今天所在月份」
          往前推 (months - 1) 個月開始 backfill，總共涵蓋 months 個月
          （含當月）——這就是 --months 3 時「約抓三個月」的由來。
        - 已有資料：從「最新資料所在月份」的第一天重新抓，不是下個月。
          這是刻意的：checkpoint 落在月中時（例如上次只抓到 7/10），
          那個月後面幾天的資料還沒抓到，必須重抓整個月才不會漏掉；
          重抓完全安全，因為 upsert 是冪等的，已經存在的日期會被同樣
          的值覆寫一次，不會產生重複列或錯誤資料。
    """
    this_month = month_start(today)
    if latest_trade_date is None:
        return add_months(this_month, -(months - 1))
    latest = date.fromisoformat(latest_trade_date)
    return month_start(latest)


def iter_months(start: date, end: date):
    """從 start 月份到 end 月份（含端點）逐月往前迭代，yield 每月第一天。"""
    current = month_start(start)
    last = month_start(end)
    while current <= last:
        yield current
        current = add_months(current, 1)


# =====================================================================
# 抓取與寫入（有 I/O）
# =====================================================================


def fetch_month(stock_symbol: str, month_first_day: date) -> list[dict] | None:
    """呼叫 TWSE STOCK_DAY API 抓一整個月的股價，回傳清理後的 rows。

    做什麼＋為什麼：
        1. 先檢查 robots.txt——即使是官方開放的 API，也照 crawlers/common.py
           的通用規範一視同仁先過這一關，不因為「反正是官方的」就跳過。
        2. 透過 polite_get() 送出請求（內建 rate limit 與 exponential
           backoff 重試），請求失敗回傳 None，由呼叫端記 log 跳過這個月，
           不能讓單一月份失敗中斷整支爬蟲（其他月份仍要繼續抓）。
        3. TWSE 對「查無資料」的月份（例如查詢未來月份）不會回一般格式的
           data，而是把 stat 設成非 "OK" 的說明文字（例如「查詢日期大於
           今日，請重新查詢!」）。這種情況視為「這個月還沒有資料」，
           回傳空 list，不當成錯誤。

    回傳：
        None    — 這個月的請求失敗（網路 / HTTP 錯誤，重試多次仍失敗）。
        []      — 請求成功，但這個月沒有可用資料（例如查詢到未來月份）。
        [dict…] — 請求成功且清理出至少一筆有效資料。
    """
    date_param = month_first_day.strftime("%Y%m%d")  # day 固定是 1，等同 YYYYMM01
    url = f"{TWSE_STOCK_DAY_URL}?response=json&date={date_param}&stockNo={stock_symbol}"

    if not check_robots_allowed(url):
        logger.warning("robots.txt 不允許抓取，跳過：%s", url)
        return None

    response = polite_get(url, logger, RATE_LIMIT_STOCK)
    if response is None:
        return None

    try:
        payload = response.json()
    except ValueError:
        logger.error("回應不是合法 JSON，跳過 %s：%s", date_param, url)
        return None

    if payload.get("stat") != "OK":
        logger.info(
            "%s 月沒有可用資料（stat=%r），略過", date_param, payload.get("stat")
        )
        return []

    raw_rows = payload.get("data", [])
    cleaned: list[dict] = []
    for raw_row in raw_rows:
        try:
            cleaned_row = clean_daily_row(stock_symbol, raw_row)
        except Exception as exc:  # noqa: BLE001 — 單筆清理失敗不可中斷整月／整批爬取
            # 注意：clean_daily_row() 內部的解析函式（convert_roc_date /
            # parse_number 等）已經用 try/except 把「格式不對」轉成安全的
            # None，正常情況不會走到這裡；這個 except 攔的是更意外的情況
            # （例如 TWSE 這一列的欄位型別跟預期不同，導致 .strip() 這類
            # 呼叫直接噴例外）。以前這裡沒有攔，一旦真的發生，例外會一路
            # 往上炸穿 crawl() 的逐月迴圈，導致這個月之後的月份全部不會
            # 被抓、checkpoint 也卡在同一個月出不去（下次執行還是從這裡
            # 重抓、還是炸掉）。記 log（含原始資料，方便回頭比對是哪裡
            # 出問題）並跳過這一筆，其餘資料照常處理。
            logger.error(
                "單筆股價資料清理時發生未預期例外，跳過：%s（錯誤：%s）",
                raw_row,
                exc,
            )
            continue
        if cleaned_row is not None:
            cleaned.append(cleaned_row)
    return cleaned


def crawl(
    months: int = DEFAULT_MONTHS,
    stock_symbol: str = DEFAULT_STOCK_SYMBOL,
    *,
    today: date | None = None,
) -> int:
    """執行一次完整的股價爬取：checkpoint → 逐月抓取 → 清理 → upsert。

    參數：
        today: 只給測試用——外部注入「今天」是哪一天，讓 crawl() 的行為
            在測試裡完全可預期，不受實際執行當下的日期影響。CLI 正常
            執行時不會傳這個參數，一律用 date.today()（真正的今天）。

    回傳：本次執行實際寫入（新增或更新）的總筆數。
    """
    repo = get_repository()
    latest_trade_date = repo.get_latest_price_date(stock_symbol)
    today = today or date.today()
    start_month = determine_start_month(latest_trade_date, months, today)

    if latest_trade_date is None:
        logger.info(
            "%s 目前無既有股價資料，從 %s 開始 backfill %d 個月",
            stock_symbol,
            start_month.isoformat(),
            months,
        )
    else:
        logger.info(
            "%s checkpoint：目前最新交易日 %s，從 %s 月重新抓取到本月",
            stock_symbol,
            latest_trade_date,
            start_month.strftime("%Y-%m"),
        )

    total_written = 0
    for month_first_day in iter_months(start_month, today):
        month_label = month_first_day.strftime("%Y-%m")
        rows = fetch_month(stock_symbol, month_first_day)
        if rows is None:
            logger.error("跳過整月（請求失敗）：%s", month_label)
            continue
        if not rows:
            continue
        written = repo.upsert_daily_prices(rows)
        total_written += written
        logger.info(
            "%s 月：清理出 %d 筆有效資料、寫入(新增/更新) %d 筆",
            month_label,
            len(rows),
            written,
        )

    logger.info("股價爬蟲執行完畢（%s），本次總計寫入 %d 筆", stock_symbol, total_written)
    return total_written


# =====================================================================
# CLI 入口
# =====================================================================


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="抓取 TWSE 每日股價資料（預設台積電 2330），寫入資料庫。"
    )
    parser.add_argument(
        "--months",
        type=int,
        default=DEFAULT_MONTHS,
        help=(
            "當資料庫完全沒有既有資料時，從今天所在月份往前 backfill "
            f"幾個月（預設 {DEFAULT_MONTHS}）。已有資料時會改用 checkpoint "
            "接續抓取，此參數不影響。"
        ),
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default=DEFAULT_STOCK_SYMBOL,
        help=f"股票代號（預設 {DEFAULT_STOCK_SYMBOL} 台積電）。",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    crawl(months=args.months, stock_symbol=args.symbol)
