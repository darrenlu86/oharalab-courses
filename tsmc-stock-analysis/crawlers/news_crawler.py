"""
crawlers/news_crawler.py — 台積電新聞爬蟲（鉅亨網，Playwright）。

做什麼：
    抓鉅亨網「台積電」標籤頁的新聞列表（標題／連結），逐篇進文章頁抓發布時間
    與首段摘要，清理後寫入 news 資料表（以 url 去重，可重複執行）。

為什麼用 Playwright（而不是 requests）：
    鉅亨網的新聞列表頁是 React SPA（Next.js App Router），初始 HTML 只帶
    少量文章，其餘新聞是瀏覽器載入後才用 client-side 邏輯補齊——實測
    plain requests/curl 抓到的 <a href="/news/id/..."> 連結數量明顯少於
    Playwright 用真瀏覽器把頁面「跑完」之後看到的數量（2026-07-22 實測：
    curl 24 筆 vs. 瀏覽器渲染後 33 筆不重複連結）。這正是本專案刻意挑這個
    來源、用 Playwright 當教學主角的原因：requests 對這種頁面會「看起來
    成功（HTTP 200）、內容卻不完整」，是初學者很容易忽略的陷阱。

取捨教學點（誠實揭露，不代表本檔案這樣做）：
    鉅亨網其實另外有公開的 JSON API（api.cnyes.com），實務上如果只是要
    抓新聞資料，直接打那組 API 會更穩定、更省資源、不用背瀏覽器的開銷。
    本專案為了教學目的刻意不用那組 API，改用「開瀏覽器把頁面渲染出來」
    這條路，示範遇到 JS 渲染網站時的標準解法。如果你在做真正的正式專案，
    看到目標網站有現成 API，通常應該優先選 API，而不是無腦上 Playwright。

架構設計（為什麼把「渲染」跟「解析」拆成兩步）：
    1. `_fetch_rendered_html()`：唯一會碰瀏覽器、碰網路的地方，用 Playwright
       打開頁面、等待內容渲染完成，回傳「渲染完成後的完整 HTML 字串」。
    2. `parse_list_items()` / `parse_detail_page()`：純函式，輸入是上一步
       拿到的 HTML 字串，用 BeautifulSoup 從裡面挑資料，不碰網路、不開瀏覽器。
    這樣拆的好處：解析邏輯可以用「事先存好的 HTML 檔案」單獨測試，測試
    跑起來快（不用真的開瀏覽器、不用等網路），也不會因為網站內容每天在
    變而讓測試變得不穩定（flaky）。這是本專案所有清理/解析函式的共同原則
    （純函式、輸入→輸出、不做 I/O），只是這裡多套了一層「先渲染、再解析」。

流程：
    check_robots_allowed（列表頁）→ 開瀏覽器 → 列表頁渲染＋解析（標題／連結，
    上限 --limit 筆，預設 20）→ check_robots_allowed（用第一篇候選文章的
    網址代表整批文章頁路徑檢查一次，見下方「注意」）→ 逐篇文章頁渲染＋
    解析（發布時間／摘要，頁面間 sleep 2 秒節流）→ 清理（標題 strip／URL
    去 tracking 參數）→ repo.upsert_news()（url 去重，因此重複執行不會
    產生重複資料）。

注意（初學者常見誤解）：
    - 單篇文章抓失敗（網路錯誤、頁面結構跟預期不同）只記 log 跳過，
      不會讓整支爬蟲中斷——見 `_fetch_rendered_html()` 的重試邏輯與
      `crawl_news()` 逐篇迴圈裡的 try/except。
    - 文章頁的 robots.txt 檢查只打一次（用第一篇候選文章的網址代表），
      不是每篇文章各打一次：同網域下所有文章頁網址都是同樣的
      /news/id/<id> 路徑樣式，robots.txt 規則本來就是針對路徑樣式表達
      允許/禁止，重複檢查同一條規則不會得到不同結論，只會多打 N-1 次
      沒有必要的 HTTP 請求。
    - 解析不到必要欄位（例如抓不到發布時間）一律跳過該筆，絕不填假值
      去湊資料，這是本專案「不捏造資料」鐵律在爬蟲層的具體實踐。
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup
from playwright.sync_api import Page, sync_playwright

# 讓本檔案可以用 `venv/bin/python -m crawlers.news_crawler` 或直接
# `venv/bin/python crawlers/news_crawler.py` 兩種方式執行都找得到專案根目錄
# 的套件（db/、config.py）。
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.common import (  # noqa: E402
    RATE_LIMIT_NEWS,
    RETRY_BACKOFF_SECONDS,
    USER_AGENT,
    check_robots_allowed,
    setup_logging,
)
from db.factory import get_repository  # noqa: E402

# --- 站台與資料常數 ---
BASE_URL = "https://news.cnyes.com"
# 標籤頁網址：候選有 /tag/台積電 與 /search?q=台積電 兩種，2026-07-22 實測
# tag 頁面單頁就能穩定渲染出 30 篇以上不重複新聞，結構也比搜尋頁單純，
# 因此選用 tag 頁；用 urljoin 組出完整網址，避免中文字元手動 percent-encode
# 打錯字。
TAG_URL = urljoin(BASE_URL, "/tag/台積電")
STOCK_SYMBOL = "2330"
SOURCE_NAME = "鉅亨網"

# 文章連結一定長這樣：/news/id/正整數。id=0 在頁面上是尚未填內容的預留卡片
# （2026-07-22 實測其文字固定顯示「--」），用這個 pattern 直接排除，
# 比用「標題字數夠不夠長」這種模糊的經驗法則更精確、更好解釋原因。
_NEWS_LINK_PATTERN = re.compile(r"^/news/id/([1-9]\d*)$")

# 常見的行銷/追蹤用 query 參數，清理 URL 時要去掉；只挑這些已知的 key 移除，
# 不是「query string 整包清空」——避免萬一網址真的帶有意義的參數（如分頁、
# 版本）被誤刪。
_TRACKING_PARAM_KEYS = {"fbclid", "gclid", "ref", "from", "spm", "igshid"}

# 摘要最長字數（規格 §5b：≤300 字）。
SUMMARY_MAX_LENGTH = 300

# Playwright 等待渲染完成的逾時秒數（毫秒）：列表頁要等 client-side 補齊
# 完整新聞清單，給比較長的時間；文章頁內容本來就在初始 HTML 裡，等短一點即可。
LIST_WAIT_TIMEOUT_MS = 15000
DETAIL_WAIT_TIMEOUT_MS = 15000


# =====================================================================
# 清理／解析純函式（輸入 → 輸出，不做 I/O，對應 tests/test_news_crawler.py）
# =====================================================================
def clean_title(title: str) -> str:
    """清理新聞標題：去除全形空白、頭尾空白。

    做什麼＋為什麼：
        中文網頁排版常見全形空白（\\u3000），肉眼看起來像正常空格，
        但字串比對／去重時會被當成完全不同的字元，所以統一換成半形空白
        後再 strip，避免資料庫裡存進「看起來正常、實際上有髒字元」的標題。
    """
    return title.replace("　", " ").strip()


def clean_news_url(url: str, base: str = BASE_URL) -> str:
    """清理新聞網址：轉成絕對網址、去掉已知的行銷追蹤參數與網址片段(#...)。

    做什麼＋為什麼：
        同一篇文章如果分享時被加上 ?fbclid=xxx 這類追蹤參數，網址字串會
        變得不一樣，但實際上是同一篇文章——upsert_news 是用 url 完整字串
        去重，如果不先清掉追蹤參數，同一篇新聞可能因為追蹤參數不同而被
        誤判成不同文章、重複寫入。

    注意：
        只移除已知的追蹤參數 key（見 _TRACKING_PARAM_KEYS），其餘 query
        參數原樣保留，避免誤刪真正有意義的參數。
    """
    absolute = urljoin(base, url.strip())
    parsed = urlparse(absolute)
    kept_params = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_PARAM_KEYS and not key.lower().startswith("utm_")
    ]
    cleaned = parsed._replace(query=urlencode(kept_params), fragment="")
    return urlunparse(cleaned)


def _to_iso_utc(dt: datetime) -> str:
    """把一個 datetime 物件統一格式化成 UTC ISO8601 字串（含 Z 結尾）。"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_RELATIVE_TIME_PATTERN = re.compile(r"^(\d+)\s*(秒|分鐘|小時|天)前$")
_MONTH_DAY_PATTERN = re.compile(r"^(\d{1,2})-(\d{1,2})$")


def parse_relative_or_absolute_time(text: str, now: datetime) -> str | None:
    """把新聞頁面上常見的各種時間文字，統一轉成 UTC ISO8601 字串。

    支援的格式（規格 §5b 要求的「相對時間→ISO8601」＋「絕對時間統一ISO8601」）：
        - 相對時間：「剛剛」「3 分鐘前」「5 小時前」「2 天前」
        - 絕對時間：「2026-07-22 21:00」「2026-07-22T13:00:03.000Z」
          「2026-07-22」
        - 只有月日、沒有年份：「07-22」（沒有更多資訊時，假設是「今年」；
          若推算出來的日期比 now 還晚，代表其實是「去年」的月日，例如
          now 是 1 月、文字是「12-31」）

    參數：
        text: 待解析的原始文字。
        now: 執行當下的時間（呼叫端傳入，方便測試時固定一個時間點，
             不必依賴真正的系統時間——這是純函式「輸入→輸出」的具體示範）。

    回傳：
        解析成功回傳 UTC ISO8601 字串（如 "2026-07-22T13:00:03Z"）；
        解析不出來回傳 None，呼叫端要記 log 並跳過，不可以硬湊一個時間。

    注意（初學者常見誤解）：
        本專案實際爬取時，時間主要直接取自文章頁 <time datetime="..."> 屬性
        （網站已經給好 ISO8601），這個函式是「網站沒給乾淨屬性時」的備援
        解析路徑，同時也是規格要求要能處理相對時間的測試對象。
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    text = text.strip()
    if not text:
        return None

    if text in ("剛剛", "剛才"):
        return _to_iso_utc(now)

    relative_match = _RELATIVE_TIME_PATTERN.match(text)
    if relative_match:
        amount = int(relative_match.group(1))
        unit = relative_match.group(2)
        delta = {
            "秒": timedelta(seconds=amount),
            "分鐘": timedelta(minutes=amount),
            "小時": timedelta(hours=amount),
            "天": timedelta(days=amount),
        }[unit]
        return _to_iso_utc(now - delta)

    # 已經是 ISO8601（含 Z 或時區資訊）：正規化格式後直接回傳。
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return _to_iso_utc(dt)
    except ValueError:
        pass

    # 絕對時間但沒有時區資訊：視為與網站 <time datetime> 屬性一致的 UTC。
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            return _to_iso_utc(dt)
        except ValueError:
            continue

    # 只有月日（如「07-22」），用執行當下年份推算，太晚就往前推一年。
    month_day_match = _MONTH_DAY_PATTERN.match(text)
    if month_day_match:
        month, day = int(month_day_match.group(1)), int(month_day_match.group(2))
        try:
            candidate = now.replace(
                month=month, day=day, hour=0, minute=0, second=0, microsecond=0
            )
        except ValueError:
            return None  # 例如 02-30 這種不存在的日期，寧可跳過也不要亂猜
        if candidate > now:
            candidate = candidate.replace(year=candidate.year - 1)
        return _to_iso_utc(candidate)

    return None


def parse_list_items(html: str, limit: int = 20) -> list[dict]:
    """從列表頁（渲染完成後）的 HTML 解析出候選新聞清單。

    做什麼：
        找出所有指向 /news/id/正整數 的連結，取其可見文字當標題，
        依照在頁面上出現的順序去重（同一篇新聞在頁面上可能因為版位重複
        出現兩次連結），最多回傳 `limit` 筆。

    回傳：
        list[dict]，每筆為 {"title": str, "url": str}（url 為絕對網址）。
        標題抓不到文字、或連結 id 是 0（頁面預留卡片，非真實文章）的項目
        會直接跳過，不會出現在回傳結果裡。
    """
    soup = BeautifulSoup(html, "html.parser")
    seen_urls: set[str] = set()
    items: list[dict] = []

    for anchor in soup.select("a[href*='/news/id/']"):
        href = anchor.get("href")
        if not href or not _NEWS_LINK_PATTERN.match(href):
            continue
        title = anchor.get_text(strip=True)
        if not title:
            continue

        absolute_url = urljoin(BASE_URL, href)
        if absolute_url in seen_urls:
            continue
        seen_urls.add(absolute_url)

        items.append({"title": title, "url": absolute_url})
        if len(items) >= limit:
            break

    return items


def parse_detail_page(html: str) -> dict:
    """從文章頁（渲染完成後）的 HTML 解析出發布時間與首段摘要。

    做什麼：
        - 發布時間：抓 <time datetime="..."> 的 datetime 屬性（鉅亨網的
          文章頁固定會渲染出這個屬性，值已經是 ISO8601），正規化格式後
          回傳；抓不到就回傳 None，交由呼叫端決定要不要跳過整筆新聞。
        - 摘要：抓文章內文容器（#article-container）底下的第一個 <p>，
          取其文字內容，截斷到 SUMMARY_MAX_LENGTH 字（規格 §5b：≤300 字）。

    回傳：
        {"published_at": str | None, "summary": str | None}
    """
    soup = BeautifulSoup(html, "html.parser")

    published_at: str | None = None
    time_tag = soup.select_one("time[datetime]")
    if time_tag is not None:
        raw_datetime = time_tag.get("datetime", "").strip()
        if raw_datetime:
            published_at = parse_relative_or_absolute_time(
                raw_datetime, now=datetime.now(timezone.utc)
            )

    summary: str | None = None
    container = soup.select_one("#article-container")
    if container is not None:
        first_paragraph = container.find("p")
        if first_paragraph is not None:
            text = first_paragraph.get_text(strip=True)
            if text:
                summary = text[:SUMMARY_MAX_LENGTH]

    return {"published_at": published_at, "summary": summary}


# =====================================================================
# I/O：Playwright 渲染頁面
# =====================================================================
def _fetch_rendered_html(
    page: Page,
    url: str,
    wait_selector: str,
    logger: logging.Logger,
    wait_timeout_ms: int,
) -> str | None:
    """開啟指定網址、等待關鍵元素渲染完成，回傳完整 HTML 字串。

    做什麼＋為什麼：
        這是本檔案唯一會碰瀏覽器、碰網路的函式（與上面一整排純函式明確
        切開）。失敗時比照 crawlers/common.py 的 polite_get() 精神——
        用 2s/4s/8s 的 exponential backoff 重試最多 3 次，每次嘗試前都先
        sleep RATE_LIMIT_NEWS 秒節流；全部重試完仍失敗就記 log 回傳 None，
        由呼叫端決定跳過這一筆、不讓整支爬蟲中斷。

    注意（初學者常見誤解）：
        沒有用 wait_until="networkidle"——鉅亨網頁面背景有持續的追蹤/輪詢
        請求，networkidle 實測會整個等到逾時（2026-07-22 實測 30 秒逾時）。
        改用 wait_until="domcontentloaded" 之後，再用 wait_for_selector()
        明確等待「我們真正需要的元素出現」，比瞎猜要 sleep 幾秒可靠。
    """
    attempts = [0, *RETRY_BACKOFF_SECONDS]
    last_error: Exception | None = None

    for retry_index, backoff in enumerate(attempts):
        if backoff:
            logger.warning(
                "頁面載入失敗，%d 秒後進行第 %d 次重試：%s", backoff, retry_index, url
            )
            time.sleep(backoff)

        time.sleep(RATE_LIMIT_NEWS)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector(wait_selector, timeout=wait_timeout_ms)
            return page.content()
        except Exception as exc:  # noqa: BLE001 — 單頁失敗不可讓整支爬蟲中斷，故意攔截所有例外
            last_error = exc
            continue

    logger.error(
        "頁面最終載入失敗（已重試 %d 次），跳過：%s（錯誤：%s）",
        len(RETRY_BACKOFF_SECONDS),
        url,
        last_error,
    )
    return None


# =====================================================================
# 主流程
# =====================================================================
def crawl_news(limit: int = 20) -> int:
    """執行一次完整的新聞爬取：列表頁 → 逐篇文章頁 → 清理 → upsert。

    參數：
        limit: 最多擷取幾篇新聞（對應 CLI 的 --limit，預設 20）。

    回傳：
        實際新增到資料庫的筆數（已存在的 url 不計入，方便驗證冪等性）。
    """
    logger = setup_logging("news_crawler")

    if not check_robots_allowed(TAG_URL):
        logger.warning("robots.txt 不允許抓取此網址，本次爬取已跳過：%s", TAG_URL)
        return 0

    repo = get_repository()
    rows: list[dict] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(user_agent=USER_AGENT)

            list_html = _fetch_rendered_html(
                page,
                TAG_URL,
                wait_selector="a[href*='/news/id/']",
                logger=logger,
                wait_timeout_ms=LIST_WAIT_TIMEOUT_MS,
            )
            if list_html is None:
                logger.error("列表頁抓取失敗，本次無法取得任何新聞")
                return 0

            candidates = parse_list_items(list_html, limit=limit)
            logger.info("列表頁解析出 %d 筆候選新聞（上限 %d）", len(candidates), limit)

            if candidates and not check_robots_allowed(candidates[0]["url"]):
                # 注意（取捨，不逐篇重複打 robots.txt）：文章頁網址都是同一個
                # 網域、同樣的 /news/id/<id> 路徑樣式，robots.txt 的規則是
                # 針對「路徑樣式」而不是「個別網址」表達允許或禁止，所以用
                # 清單裡第一篇文章的網址當代表，檢查一次就足以代表所有文章頁
                # 的結果——對每一篇都各打一次 robots.txt 只是多花 N-1 次
                # HTTP 請求，不會得到不同的結論。若之後改抓一個「不同文章
                # 路徑對應不同 robots 規則」的網站，才需要改回逐篇檢查。
                logger.warning(
                    "robots.txt 不允許抓取文章頁路徑，本次跳過全部 %d 篇候選文章：%s",
                    len(candidates),
                    candidates[0]["url"],
                )
                candidates = []

            for candidate in candidates:
                try:
                    detail_html = _fetch_rendered_html(
                        page,
                        candidate["url"],
                        wait_selector="#article-container",
                        logger=logger,
                        wait_timeout_ms=DETAIL_WAIT_TIMEOUT_MS,
                    )
                    if detail_html is None:
                        logger.warning("文章頁抓取失敗，跳過：%s", candidate["url"])
                        continue

                    detail = parse_detail_page(detail_html)
                    if not detail["published_at"]:
                        # 不捏造資料：抓不到發布時間就整筆跳過，不用「現在
                        # 時間」湊數。
                        logger.warning("解析不到發布時間，跳過：%s", candidate["url"])
                        continue

                    rows.append(
                        {
                            "stock_symbol": STOCK_SYMBOL,
                            "title": clean_title(candidate["title"]),
                            "url": clean_news_url(candidate["url"]),
                            "source": SOURCE_NAME,
                            "published_at": detail["published_at"],
                            "summary": detail["summary"],
                        }
                    )
                except Exception as exc:  # noqa: BLE001 — 單篇文章處理失敗不可讓已抓到的整批新聞跟著遺失
                    # 以前這裡沒有攔：parse_detail_page() 或清理函式若對某一篇
                    # 文章的頁面結構噴出未預期例外，會直接讓 crawl_news() 整個
                    # 中斷，連同這一篇之前已經處理好、還放在 rows 裡的所有文章
                    # 都一起遺失（因為還沒走到最後的 repo.upsert_news(rows)）。
                    logger.error(
                        "處理單篇文章時發生未預期例外，跳過：%s（錯誤：%s）",
                        candidate["url"],
                        exc,
                        exc_info=True,
                    )
                    continue
        finally:
            browser.close()

    new_count = repo.upsert_news(rows)
    logger.info(
        "新聞爬蟲完成：本次解析 %d 筆、成功新增 %d 筆（重複的 url 不會重複寫入）",
        len(rows),
        new_count,
    )
    return new_count


def main() -> None:
    """CLI 入口：venv/bin/python -m crawlers.news_crawler --limit 20"""
    parser = argparse.ArgumentParser(description="鉅亨網台積電新聞爬蟲")
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="最多擷取幾篇新聞（預設 20）",
    )
    args = parser.parse_args()
    crawl_news(limit=args.limit)


if __name__ == "__main__":
    main()
