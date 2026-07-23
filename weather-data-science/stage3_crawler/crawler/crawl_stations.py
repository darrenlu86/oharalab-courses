"""關卡一：靜態 HTML 解析——爬 /stations 測站清單。

這是全部關卡裡最單純的一支：一個請求、一張表格、沒有分頁。用來練習
BeautifulSoup 的基本用法（`find`/`find_all`），也是後面幾支關卡（都要多做
一件事：翻頁或列表→詳情）的對照組。
"""

from __future__ import annotations

import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from stage3_crawler.crawler.db import get_connection, upsert_station  # noqa: E402
from stage3_crawler.crawler.http_client import PoliteSession  # noqa: E402

DEFAULT_BASE_URL = "http://127.0.0.1:8310"


def parse_stations_html(html: str) -> list[dict]:
    """從 /stations 頁面的 HTML 解析出測站清單（不連網路，供測試用固定樣本呼叫）。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="stations-table")
    rows = []
    for tr in table.find("tbody").find_all("tr"):
        cells = tr.find_all("td")
        rows.append(
            {
                "city": cells[0].text.strip(),
                "name_zh": cells[1].text.strip(),
                "latitude": float(cells[2].text.strip()),
                "longitude": float(cells[3].text.strip()),
            }
        )
    return rows


def crawl(session: PoliteSession | None = None, base_url: str = DEFAULT_BASE_URL, conn=None) -> list[dict]:
    """實際爬取（需要沙盒站在跑），upsert 進 stations 表，回傳解析出的測站清單。"""
    own_session = session is None
    if own_session:
        session = PoliteSession(base_url)
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    try:
        resp = session.get("/stations")
        stations = parse_stations_html(resp.text)
        for s in stations:
            upsert_station(conn, s["city"], s["name_zh"], s["latitude"], s["longitude"])
        return stations
    finally:
        if own_session:
            session.close()
        if own_conn:
            conn.close()


def main() -> int:
    stations = crawl()
    print(f"stations 爬取完成：{len(stations)} 筆（{', '.join(s['city'] for s in stations)}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
