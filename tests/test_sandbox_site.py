"""測試教學沙盒網站 sandbox_site（FastAPI TestClient，不需要真的起 server）。

天氣資料讀 data/raw（真實）、留言/公告讀 data/synthetic（合成）——這裡直接用
repo 裡現成的 data/ 內容測試，不另外造假資料，因為 sandbox_site 本來就是
「啟動時讀現成 CSV 進記憶體」的簡單教具，沒有需要隔離的外部副作用。
"""

import sys
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sandbox_site.app import app  # noqa: E402
from sandbox_site.app import data as app_data  # noqa: E402

client = TestClient(app)

ALL_PAGES = [
    "/",
    "/stations",
    "/records?city=taipei&page=1",
    "/comments?page=1",
    "/comments?city=taichung&page=1",
    "/announcements",
    "/announcements/a01",
    "/robots.txt",
    "/api/latest?city=taipei",
]


@pytest.mark.parametrize("path", ALL_PAGES)
def test_pages_return_200(path):
    resp = client.get(path)
    assert resp.status_code == 200


def test_stations_table_has_three_rows():
    resp = client.get("/stations")
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="stations-table")
    rows = table.find("tbody").find_all("tr")
    assert len(rows) == 3
    cities = {row.find_all("td")[0].text.strip() for row in rows}
    assert cities == {"taipei", "taichung", "kaohsiung"}


def test_records_first_page_has_50_rows_and_next_link():
    resp = client.get("/records?city=taipei&page=1")
    assert resp.status_code == 200
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="records-table")
    rows = table.find("tbody").find_all("tr")
    assert len(rows) == 50
    assert soup.find("a", href="/records?city=taipei&page=2") is not None
    # 第一頁沒有「上一頁」連結
    assert soup.find("a", href="/records?city=taipei&page=0") is None


def test_records_out_of_range_page_returns_empty_table_but_200():
    resp = client.get("/records?city=taipei&page=99999")
    assert resp.status_code == 200
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="records-table")
    assert table.find("tbody").find_all("tr") == []


def test_records_unknown_city_returns_404():
    resp = client.get("/records?city=nowhere&page=1")
    assert resp.status_code == 404


def test_comments_rows_have_valid_rating():
    resp = client.get("/comments?page=1")
    assert resp.status_code == 200
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="comments-table")
    rows = table.find("tbody").find_all("tr")
    assert len(rows) == 50
    for row in rows:
        cells = row.find_all("td")
        rating_text = cells[3].text.strip()
        assert rating_text in {"1", "2", "3", "4", "5"}


def test_comments_filtered_by_city():
    resp = client.get("/comments?city=kaohsiung&page=1")
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="comments-table")
    rows = table.find("tbody").find_all("tr")
    assert rows  # 高雄留言數 > 0
    for row in rows:
        city_cell = row.find_all("td")[1].text.strip()
        assert city_cell == "kaohsiung"


def test_announcements_list_contains_all_30():
    resp = client.get("/announcements")
    soup = BeautifulSoup(resp.text, "html.parser")
    links = soup.select("ul.plain-list a")
    assert len(links) == 30


def test_announcement_detail_contains_title_and_body():
    ann = app_data.announcements_by_id["a01"]
    resp = client.get("/announcements/a01")
    assert resp.status_code == 200
    assert ann["title"] in resp.text
    assert ann["body"] in resp.text


def test_announcement_detail_unknown_id_returns_404():
    resp = client.get("/announcements/zzz")
    assert resp.status_code == 404


def test_api_latest_returns_30_json_records():
    resp = client.get("/api/latest?city=taipei")
    assert resp.status_code == 200
    payload = resp.json()
    assert isinstance(payload, list)
    assert len(payload) == 30
    assert "date" in payload[0]


def test_api_latest_unknown_city_returns_404():
    resp = client.get("/api/latest?city=nowhere")
    assert resp.status_code == 404


def test_robots_txt_allows_all():
    resp = client.get("/robots.txt")
    assert resp.status_code == 200
    assert "User-agent: *" in resp.text
    assert "Allow: /" in resp.text


def test_every_page_has_sandbox_footer():
    for path in ["/", "/stations", "/comments?page=1", "/announcements"]:
        resp = client.get(path)
        assert "本站為教學沙盒網站" in resp.text
        assert "合成資料" in resp.text
