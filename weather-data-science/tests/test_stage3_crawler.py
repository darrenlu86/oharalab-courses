"""測試 stage3_crawler：純解析函式（讀 tests/fixtures/ 固定 HTML/JSON，
不連網路）+ db.py 的 upsert 冪等性（用 conftest.py 的 fresh_db_conn）。

不測 http_client.PoliteSession 真的連網路，也不測 run_all.py/export_csv.py
（那兩支需要沙盒站在跑，屬於 SPEC §7 講的 E2E 驗證範疇，另由驗證流程執行，
不在 pytest 內；本檔的 report.md 記錄了實際跑過的結果）。
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "stage3_crawler"

from stage3_crawler.crawler import (  # noqa: E402
    crawl_announcements,
    crawl_comments,
    crawl_latest_api,
    crawl_records,
    crawl_stations,
    db,
)
from stage3_crawler.crawler.http_client import PoliteSession, parse_robots_txt  # noqa: E402


def _fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# http_client：robots.txt 解析
# ---------------------------------------------------------------------------


def test_parse_robots_txt_allows_all_paths_on_sandbox_fixture():
    robots_text = _fixture("robots.txt")
    result = parse_robots_txt(robots_text, ["/stations", "/records", "/comments", "/announcements", "/api/latest"])
    assert all(result.values()), f"預期沙盒站 robots.txt 全部允許，實際：{result}"


def test_parse_robots_txt_disallows_blocked_path():
    robots_text = "User-agent: *\nDisallow: /admin\nAllow: /\n"
    result = parse_robots_txt(robots_text, ["/admin", "/stations"])
    assert result["/admin"] is False
    assert result["/stations"] is True


# ---------------------------------------------------------------------------
# crawl_stations：關卡一
# ---------------------------------------------------------------------------


def test_parse_stations_html_returns_three_known_stations():
    stations = crawl_stations.parse_stations_html(_fixture("stations.html"))
    assert len(stations) == 3
    by_city = {s["city"]: s for s in stations}
    assert by_city["taipei"]["name_zh"] == "台北"
    assert by_city["taipei"]["latitude"] == pytest.approx(25.0330)
    assert by_city["kaohsiung"]["longitude"] == pytest.approx(120.3014)


# ---------------------------------------------------------------------------
# crawl_records：關卡二（翻頁），驗證第一頁與最後一頁
# ---------------------------------------------------------------------------


def test_parse_records_first_page_has_50_rows_and_correct_pagination():
    rows, page, total_pages = crawl_records.parse_records_page(_fixture("records_page1.html"))
    assert len(rows) == 50
    assert page == 1
    assert total_pages == 81  # 4018 天 / 50 列每頁 = 81 頁（向上取整）


def test_parse_records_first_row_matches_known_real_value():
    rows, _, _ = crawl_records.parse_records_page(_fixture("records_page1.html"))
    first = rows[0]
    # 對照 data/raw/taipei.csv 第一列（2015-01-01）的真實數值。
    assert first["date"] == "2015-01-01"
    assert first["temp_max"] == pytest.approx(13.4)
    assert first["temp_min"] == pytest.approx(10.7)
    assert first["wind_dir"] == 57


def test_parse_records_last_page_has_18_rows_and_is_final_page():
    rows, page, total_pages = crawl_records.parse_records_page(_fixture("records_page81_last.html"))
    assert page == 81
    assert total_pages == 81
    assert len(rows) == 18  # 4018 - 80*50 = 18


# ---------------------------------------------------------------------------
# crawl_comments：翻頁第二例
# ---------------------------------------------------------------------------


def test_parse_comments_first_page_has_50_rows():
    rows, page, total_pages = crawl_comments.parse_comments_page(_fixture("comments_page1.html"))
    assert len(rows) == 50
    assert page == 1
    assert total_pages == 48  # 2400 / 50 = 48（整除，無餘頁）
    for row in rows:
        assert row["rating"] in {1, 2, 3, 4, 5}
        assert row["comment_key"].startswith("c")
        assert row["content"]  # 非空字串


# ---------------------------------------------------------------------------
# crawl_announcements：列表→詳情兩層
# ---------------------------------------------------------------------------


def test_parse_announcements_list_returns_30_items_with_urls():
    items = crawl_announcements.parse_announcements_list(_fixture("announcements_list.html"))
    assert len(items) == 30
    assert all(item["url"].startswith("/announcements/") for item in items)
    assert {item["ann_id"] for item in items} == {f"a{n:02d}" for n in range(1, 31)}


def test_parse_announcement_detail_extracts_all_fields():
    detail = crawl_announcements.parse_announcement_detail(_fixture("announcement_detail_a01.html"))
    assert detail["ann_id"] == "a01"
    assert detail["title"]
    assert detail["body"]
    assert detail["published_at"]  # 非空，格式在 SPEC 裡定義為 YYYY-MM-DD 落在 2024~2025


def test_parse_announcement_detail_bad_meta_format_raises():
    bad_html = "<article><h1>t</h1><small>格式不對</small><p>x</p><p>body</p></article>"
    with pytest.raises(ValueError):
        crawl_announcements.parse_announcement_detail(bad_html)


# ---------------------------------------------------------------------------
# crawl_latest_api：JSON API
# ---------------------------------------------------------------------------


def test_parse_latest_json_returns_30_rows_with_correct_types():
    payload = json.loads(_fixture("latest_taipei.json"))
    rows = crawl_latest_api.parse_latest_json(payload)
    assert len(rows) == 30
    for row in rows:
        assert isinstance(row["temp_max"], float)
        assert isinstance(row["wind_dir"], int)


def test_parse_latest_json_handles_missing_value_as_none():
    payload = [
        {
            "date": "2099-01-01",
            "temperature_2m_max": "20.0",
            "temperature_2m_min": "10.0",
            "temperature_2m_mean": "15.0",
            "precipitation_sum": "",
            "rain_sum": "0.0",
            "precipitation_hours": "0.0",
            "windspeed_10m_max": "5.0",
            "windgusts_10m_max": "10.0",
            "winddirection_10m_dominant": "180",
            "shortwave_radiation_sum": "10.0",
        }
    ]
    rows = crawl_latest_api.parse_latest_json(payload)
    assert rows[0]["precipitation_mm"] is None


# ---------------------------------------------------------------------------
# db.py：upsert 冪等性（用 conftest.py 的 fresh_db_conn，真正落地到 SQLite）
# ---------------------------------------------------------------------------


def test_upsert_station_is_idempotent(fresh_db_conn):
    db.upsert_station(fresh_db_conn, "taipei", "台北", 25.0330, 121.5654)
    count_before = fresh_db_conn.execute("SELECT COUNT(*) FROM stations WHERE city='taipei'").fetchone()[0]
    db.upsert_station(fresh_db_conn, "taipei", "台北", 25.0330, 121.5654)
    count_after = fresh_db_conn.execute("SELECT COUNT(*) FROM stations WHERE city='taipei'").fetchone()[0]
    assert count_before == count_after == 1


def test_upsert_daily_weather_updates_on_conflict(fresh_db_conn):
    row = {
        "city": "taipei", "date": "2020-01-01", "temp_max": 20.0, "temp_min": 10.0, "temp_mean": 15.0,
        "precipitation_mm": 0.0, "rain_mm": 0.0, "precip_hours": 0.0, "windspeed_max": 5.0,
        "windgusts_max": 10.0, "wind_dir": 180, "radiation": 10.0,
    }
    db.upsert_daily_weather(fresh_db_conn, row)
    updated_row = dict(row, temp_max=99.9)  # 同一天，但溫度值被「更新」
    db.upsert_daily_weather(fresh_db_conn, updated_row)

    result = fresh_db_conn.execute(
        "SELECT COUNT(*), MAX(temp_max) FROM daily_weather WHERE city='taipei' AND date='2020-01-01'"
    ).fetchone()
    assert result[0] == 1  # 沒有變成兩列
    assert result[1] == pytest.approx(99.9)  # 值真的被覆寫（ON CONFLICT DO UPDATE）


def test_upsert_comment_ignores_conflict_keeps_original_content(fresh_db_conn):
    db.upsert_comment(fresh_db_conn, "c9999", "taipei", "2020-01-01", 5, "原始內容", "2026-01-01T00:00:00")
    db.upsert_comment(fresh_db_conn, "c9999", "taipei", "2020-01-01", 1, "被改過的內容", "2026-02-02T00:00:00")

    result = fresh_db_conn.execute(
        "SELECT COUNT(*), content, rating FROM comments WHERE comment_key='c9999'"
    ).fetchall()
    assert len(result) == 1
    assert result[0][1] == "原始內容"  # INSERT OR IGNORE：第二次沒有覆寫
    assert result[0][2] == 5


def test_upsert_announcement_is_idempotent(fresh_db_conn):
    db.upsert_announcement(fresh_db_conn, "a99", "標題", "內文", "2025-01-01")
    db.upsert_announcement(fresh_db_conn, "a99", "標題", "內文", "2025-01-01")
    count = fresh_db_conn.execute("SELECT COUNT(*) FROM announcements WHERE ann_key='a99'").fetchone()[0]
    assert count == 1


def test_table_row_counts_returns_all_five_tables(fresh_db_conn):
    counts = db.table_row_counts(fresh_db_conn)
    assert set(counts.keys()) == {"stations", "daily_weather", "comments", "announcements", "predictions"}
    assert counts["stations"] == 3  # fresh_db 已經跑過 init_db，含三個預設測站


# ---------------------------------------------------------------------------
# http_client.PoliteSession：重試邏輯（注入假的底層 session.get，不連網路）
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, text="ok", json_data=None):
        self.text = text
        self._json = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


def test_polite_session_get_retries_then_succeeds(monkeypatch):
    import requests as requests_module

    session = PoliteSession("http://127.0.0.1:9999", delay_seconds=0, max_retries=2)
    calls = {"count": 0}

    def fake_get(url, params=None, timeout=None):
        calls["count"] += 1
        if calls["count"] <= 2:
            raise requests_module.exceptions.Timeout("模擬逾時")
        return _FakeResponse(text="成功")

    monkeypatch.setattr(session.session, "get", fake_get)
    resp = session.get("/stations")
    assert resp.text == "成功"
    assert calls["count"] == 3


def test_polite_session_get_gives_up_after_max_retries(monkeypatch):
    import requests as requests_module

    session = PoliteSession("http://127.0.0.1:9999", delay_seconds=0, max_retries=2)

    def always_fail(url, params=None, timeout=None):
        raise requests_module.exceptions.ConnectionError("模擬連線失敗")

    monkeypatch.setattr(session.session, "get", always_fail)
    with pytest.raises(RuntimeError):
        session.get("/stations")


def test_polite_session_base_url_join_strips_slashes():
    session = PoliteSession("http://127.0.0.1:8310/", delay_seconds=0)
    assert session.base_url == "http://127.0.0.1:8310"
