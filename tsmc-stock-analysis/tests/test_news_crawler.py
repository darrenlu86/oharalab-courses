"""
tests/test_news_crawler.py — 驗證 crawlers/news_crawler.py 的清理／解析純函式。

涵蓋範圍：
    - clean_title / clean_news_url：字串清理，不碰網路。
    - parse_relative_or_absolute_time：相對時間／絕對時間 → ISO8601。
    - parse_list_items / parse_detail_page：用固定 HTML fixture 測解析，
      不開瀏覽器、不打網路（fixture 檔案見 tests/fixtures/news_*.html）。
    - crawl_news()：用假的 Playwright／repository 物件模擬「單篇文章處理
      失敗」與「文章頁 robots 檢查」兩種情境，驗證整批流程的錯誤隔離行為
      （不開真瀏覽器、不打真網路，見下方 _install_fake_playwright()）。

為什麼這樣設計：
    news_crawler.py 特意把「開瀏覽器渲染頁面」（I/O）與「從 HTML 挑資料」
    （純函式）拆成兩層，測試只測後者——這樣測試跑起來快、穩定，也不會因為
    鉅亨網頁面內容每天在變而讓測試失敗（詳見該檔案模組 docstring）。
    crawl_news() 的錯誤隔離行為則是用假物件（monkeypatch 掉 sync_playwright
    / _fetch_rendered_html / parse_detail_page / get_repository）模擬，
    同樣不需要真的開瀏覽器打網路。
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from crawlers import news_crawler as nc
from crawlers.news_crawler import (
    clean_news_url,
    clean_title,
    parse_detail_page,
    parse_list_items,
    parse_relative_or_absolute_time,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def _install_fake_playwright(monkeypatch) -> None:
    """把 crawl_news() 會用到的 sync_playwright 換成假物件，不真的開瀏覽器。

    做什麼＋為什麼：
        crawl_news() 內部是 `with sync_playwright() as playwright:
        browser = playwright.chromium.launch(...); page = browser.new_page(...)`，
        這裡用一組最小的假物件滿足這幾行程式碼需要的介面（__enter__／
        chromium.launch()／new_page()／close()），讓 crawl_news() 可以整支
        函式真的被呼叫、跑到 repo.upsert_news() 為止，但完全不會真的打開
        瀏覽器或連網路——實際的頁面內容改由各測試自己 monkeypatch
        `_fetch_rendered_html` 與 `parse_detail_page` 提供。
    """

    class _FakePage:
        pass

    class _FakeBrowser:
        def new_page(self, user_agent=None):
            return _FakePage()

        def close(self):
            pass

    class _FakeChromium:
        def launch(self, headless=True):
            return _FakeBrowser()

    class _FakePlaywrightHandle:
        chromium = _FakeChromium()

    class _FakePlaywrightContext:
        def __enter__(self):
            return _FakePlaywrightHandle()

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    monkeypatch.setattr(nc, "sync_playwright", lambda: _FakePlaywrightContext())


class _FakeRepo:
    """假的 repository：只記錄 upsert_news() 被呼叫時收到哪些 rows。"""

    def __init__(self):
        self.saved_rows: list[dict] | None = None

    def upsert_news(self, rows: list[dict]) -> int:
        self.saved_rows = rows
        return len(rows)


# ---------------------------------------------------------------
# clean_title
# ---------------------------------------------------------------
def test_clean_title_strips_and_replaces_fullwidth_space():
    # 　 是全形空白，肉眼看起來像正常空格，容易被忽略。
    dirty = "　台積電法說會展望樂觀　"
    assert clean_title(dirty) == "台積電法說會展望樂觀"


def test_clean_title_strips_ordinary_whitespace():
    assert clean_title("  外資調升目標價\n") == "外資調升目標價"


# ---------------------------------------------------------------
# clean_news_url
# ---------------------------------------------------------------
def test_clean_news_url_converts_relative_to_absolute():
    assert (
        clean_news_url("/news/id/9001001")
        == "https://news.cnyes.com/news/id/9001001"
    )


def test_clean_news_url_strips_tracking_params_but_keeps_others():
    dirty = "https://news.cnyes.com/news/id/9001001?fbclid=abc&utm_source=line&page=2"
    cleaned = clean_news_url(dirty)
    assert "fbclid" not in cleaned
    assert "utm_source" not in cleaned
    assert "page=2" in cleaned  # 非追蹤參數應該保留，不是整包 query 清空


def test_clean_news_url_strips_fragment():
    assert (
        clean_news_url("https://news.cnyes.com/news/id/9001001#comments")
        == "https://news.cnyes.com/news/id/9001001"
    )


# ---------------------------------------------------------------
# parse_relative_or_absolute_time
# ---------------------------------------------------------------
def test_parse_relative_time_hours_ago():
    now = datetime(2026, 7, 22, 15, 0, 0, tzinfo=timezone.utc)
    assert parse_relative_or_absolute_time("3小時前", now) == "2026-07-22T12:00:00Z"


def test_parse_relative_time_minutes_ago():
    now = datetime(2026, 7, 22, 15, 0, 0, tzinfo=timezone.utc)
    assert parse_relative_or_absolute_time("45分鐘前", now) == "2026-07-22T14:15:00Z"


def test_parse_relative_time_days_ago():
    now = datetime(2026, 7, 22, 15, 0, 0, tzinfo=timezone.utc)
    assert parse_relative_or_absolute_time("2天前", now) == "2026-07-20T15:00:00Z"


def test_parse_relative_time_just_now():
    now = datetime(2026, 7, 22, 15, 0, 0, tzinfo=timezone.utc)
    assert parse_relative_or_absolute_time("剛剛", now) == "2026-07-22T15:00:00Z"


def test_parse_absolute_time_with_iso_z_suffix():
    now = datetime(2026, 7, 22, 15, 0, 0, tzinfo=timezone.utc)
    result = parse_relative_or_absolute_time("2026-07-22T13:00:03.000Z", now)
    assert result == "2026-07-22T13:00:03Z"


def test_parse_absolute_time_with_space_separator():
    now = datetime(2026, 7, 22, 15, 0, 0, tzinfo=timezone.utc)
    result = parse_relative_or_absolute_time("2026-07-22 21:00", now)
    assert result == "2026-07-22T21:00:00Z"


def test_parse_month_day_only_assumes_current_year():
    now = datetime(2026, 7, 22, 15, 0, 0, tzinfo=timezone.utc)
    result = parse_relative_or_absolute_time("07-21", now)
    assert result == "2026-07-21T00:00:00Z"


def test_parse_month_day_only_rolls_back_a_year_when_in_future():
    # now 是 1 月，文字卻是「12-31」：代表其實是去年的 12 月 31 日。
    now = datetime(2026, 1, 5, 0, 0, 0, tzinfo=timezone.utc)
    result = parse_relative_or_absolute_time("12-31", now)
    assert result == "2025-12-31T00:00:00Z"


def test_parse_unrecognized_text_returns_none():
    now = datetime(2026, 7, 22, 15, 0, 0, tzinfo=timezone.utc)
    assert parse_relative_or_absolute_time("這不是時間格式", now) is None


def test_parse_empty_text_returns_none():
    now = datetime(2026, 7, 22, 15, 0, 0, tzinfo=timezone.utc)
    assert parse_relative_or_absolute_time("", now) is None


# ---------------------------------------------------------------
# parse_list_items（固定 HTML fixture，不打網路）
# ---------------------------------------------------------------
def test_parse_list_items_extracts_title_and_url():
    html = _read_fixture("news_list_page.html")
    items = parse_list_items(html, limit=20)

    urls = [item["url"] for item in items]
    assert "https://news.cnyes.com/news/id/9001001" in urls
    first = next(i for i in items if i["url"].endswith("9001001"))
    assert first["title"] == "示範標題：台積電法說會展望樂觀"


def test_parse_list_items_dedupes_same_url():
    html = _read_fixture("news_list_page.html")
    items = parse_list_items(html, limit=20)
    urls = [item["url"] for item in items]
    # fixture 裡 9001001 因版位重複出現兩次連結，去重後應只剩一筆。
    assert urls.count("https://news.cnyes.com/news/id/9001001") == 1


def test_parse_list_items_excludes_placeholder_id_zero():
    html = _read_fixture("news_list_page.html")
    items = parse_list_items(html, limit=20)
    urls = [item["url"] for item in items]
    assert not any(url.endswith("/news/id/0") for url in urls)


def test_parse_list_items_excludes_empty_title_links():
    html = _read_fixture("news_list_page.html")
    items = parse_list_items(html, limit=20)
    urls = [item["url"] for item in items]
    # 9001005 只有 <img>、沒有文字標題，應該被排除。
    assert "https://news.cnyes.com/news/id/9001005" not in urls


def test_parse_list_items_respects_limit():
    html = _read_fixture("news_list_page.html")
    items = parse_list_items(html, limit=2)
    assert len(items) == 2


# ---------------------------------------------------------------
# parse_detail_page（固定 HTML fixture，不打網路）
# ---------------------------------------------------------------
def test_parse_detail_page_extracts_published_at():
    html = _read_fixture("news_detail_page.html")
    result = parse_detail_page(html)
    assert result["published_at"] == "2026-07-22T13:00:03Z"


def test_parse_detail_page_truncates_summary_to_max_length():
    html = _read_fixture("news_detail_page.html")
    result = parse_detail_page(html)
    assert result["summary"] is not None
    assert len(result["summary"]) <= 300


def test_parse_detail_page_only_takes_first_paragraph():
    html = _read_fixture("news_detail_page.html")
    result = parse_detail_page(html)
    assert "相關報導" not in result["summary"]


def test_parse_detail_page_missing_time_returns_none():
    html = "<main id='article-container'><p>沒有時間標籤的內文</p></main>"
    result = parse_detail_page(html)
    assert result["published_at"] is None
    assert result["summary"] == "沒有時間標籤的內文"


def test_parse_detail_page_missing_article_container_returns_none_summary():
    html = "<time datetime='2026-07-22T13:00:03.000Z'>2026-07-22 21:00</time>"
    result = parse_detail_page(html)
    assert result["published_at"] == "2026-07-22T13:00:03Z"
    assert result["summary"] is None


# ---------------------------------------------------------------
# crawl_news()：單篇文章例外隔離、文章頁 robots 檢查（假 Playwright，不打網路）
# ---------------------------------------------------------------
def test_crawl_news_single_article_exception_does_not_lose_batch(monkeypatch):
    """一篇文章在處理時真的拋出例外（不是回傳 None 那種正常的「抓不到」），
    其餘文章仍要正常入庫——不能因為單篇的未預期例外，讓已經抓到、還沒寫進
    資料庫的整批新聞一起遺失。"""
    monkeypatch.setattr(nc, "check_robots_allowed", lambda url: True)
    _install_fake_playwright(monkeypatch)

    candidates = [
        {"title": "好文章1", "url": "https://news.cnyes.com/news/id/1"},
        {"title": "壞文章", "url": "https://news.cnyes.com/news/id/2"},
        {"title": "好文章2", "url": "https://news.cnyes.com/news/id/3"},
    ]
    monkeypatch.setattr(nc, "parse_list_items", lambda html, limit: candidates)

    # 直接把 url 當「html」內容回傳，方便下面依 url 判斷要不要模擬例外。
    monkeypatch.setattr(
        nc,
        "_fetch_rendered_html",
        lambda page, url, wait_selector, logger, wait_timeout_ms: url,
    )

    def fake_parse_detail_page(html: str) -> dict:
        if "id/2" in html:
            raise ValueError("模擬解析單篇文章時的未預期例外")
        return {"published_at": "2026-07-22T00:00:00Z", "summary": "摘要"}

    monkeypatch.setattr(nc, "parse_detail_page", fake_parse_detail_page)

    fake_repo = _FakeRepo()
    monkeypatch.setattr(nc, "get_repository", lambda: fake_repo)

    new_count = nc.crawl_news(limit=20)

    assert new_count == 2
    assert fake_repo.saved_rows is not None
    saved_urls = [row["url"] for row in fake_repo.saved_rows]
    assert "https://news.cnyes.com/news/id/1" in saved_urls
    assert "https://news.cnyes.com/news/id/3" in saved_urls
    assert "https://news.cnyes.com/news/id/2" not in saved_urls


def test_crawl_news_skips_all_articles_when_robots_disallows_article_path(monkeypatch):
    """robots.txt 對文章頁路徑禁止時，應該直接跳過所有候選文章，完全不會
    去打開任何一篇文章頁（用第一篇候選文章的網址代表檢查一次，見
    news_crawler.py 模組 docstring 的取捨說明）。"""
    fetched_urls: list[str] = []

    def fake_check_robots_allowed(url: str) -> bool:
        if url == nc.TAG_URL:
            return True  # 列表頁本身允許抓取
        return False  # 文章頁路徑不允許

    monkeypatch.setattr(nc, "check_robots_allowed", fake_check_robots_allowed)
    _install_fake_playwright(monkeypatch)

    candidates = [{"title": "文章1", "url": "https://news.cnyes.com/news/id/1"}]
    monkeypatch.setattr(nc, "parse_list_items", lambda html, limit: candidates)

    def fake_fetch_rendered_html(page, url, wait_selector, logger, wait_timeout_ms):
        fetched_urls.append(url)
        return "<html>list</html>"

    monkeypatch.setattr(nc, "_fetch_rendered_html", fake_fetch_rendered_html)

    fake_repo = _FakeRepo()
    monkeypatch.setattr(nc, "get_repository", lambda: fake_repo)

    new_count = nc.crawl_news(limit=20)

    assert new_count == 0
    # 只有列表頁被渲染過，文章頁完全沒被打開過——robots 檢查在進文章頁
    # 迴圈前就先擋下了。
    assert fetched_urls == [nc.TAG_URL]
