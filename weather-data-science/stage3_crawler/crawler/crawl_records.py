"""關卡二：翻頁爬蟲——爬 /records?city=&page= 歷史每日觀測，寫進 daily_weather。

跟關卡一（/stations）比,多了一件事：怎麼知道爬到最後一頁該停下來。這裡
用頁面本身印出的「第 X 頁 / 共 Y 頁」文字解析出總頁數,爬完 1..總頁數就
停止,不用「爬到空表格才發現爬過頭」這種土法煉鋼的方式。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from stage3_crawler.crawler.db import get_connection, upsert_daily_weather  # noqa: E402
from stage3_crawler.crawler.http_client import PoliteSession  # noqa: E402

DEFAULT_BASE_URL = "http://127.0.0.1:8310"
CITIES = ["taipei", "taichung", "kaohsiung"]

# HTML 表格欄名（API 原樣命名） -> daily_weather 表欄名（SPEC §3.3 schema）。
API_TO_DB_COLUMN = {
    "temperature_2m_max": "temp_max",
    "temperature_2m_min": "temp_min",
    "temperature_2m_mean": "temp_mean",
    "precipitation_sum": "precipitation_mm",
    "rain_sum": "rain_mm",
    "precipitation_hours": "precip_hours",
    "windspeed_10m_max": "windspeed_max",
    "windgusts_10m_max": "windgusts_max",
    "winddirection_10m_dominant": "wind_dir",
    "shortwave_radiation_sum": "radiation",
}

PAGE_CAPTION_PATTERN = re.compile(r"第\s*(\d+)\s*頁\s*/\s*共\s*(\d+)\s*頁")


def parse_records_page(html: str) -> tuple[list[dict], int, int]:
    """解析 /records 頁面：回傳（該頁列的 dict 清單, 目前頁碼, 總頁數）。

    每個 dict 已經把欄名從 API 命名轉成 daily_weather 表命名（不含
    city，呼叫端知道自己在爬哪個城市，不需要從 HTML 反推）。
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="records-table")
    caption_match = PAGE_CAPTION_PATTERN.search(table.find("caption").text)
    page, total_pages = int(caption_match.group(1)), int(caption_match.group(2))

    headers = [th.text.strip() for th in table.find("thead").find_all("th")]
    rows = []
    for tr in table.find("tbody").find_all("tr"):
        cells = [td.text.strip() for td in tr.find_all("td")]
        raw = dict(zip(headers, cells))
        row = {"date": raw["date"]}
        for api_col, db_col in API_TO_DB_COLUMN.items():
            value = raw.get(api_col, "")
            row[db_col] = float(value) if db_col != "wind_dir" else int(float(value)) if value else None
        rows.append(row)
    return rows, page, total_pages


def crawl_city(city: str, session: PoliteSession | None = None, base_url: str = DEFAULT_BASE_URL, conn=None) -> int:
    """爬單一城市全部頁面,upsert 進 daily_weather,回傳寫入的列數。"""
    own_session = session is None
    if own_session:
        session = PoliteSession(base_url)
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    total_rows = 0
    try:
        page = 1
        total_pages = 1
        while page <= total_pages:
            resp = session.get("/records", params={"city": city, "page": page})
            rows, current_page, total_pages = parse_records_page(resp.text)
            for row in rows:
                row["city"] = city
                upsert_daily_weather(conn, row)
            total_rows += len(rows)
            page += 1
        return total_rows
    finally:
        if own_session:
            session.close()
        if own_conn:
            conn.close()


def crawl_all_cities(base_url: str = DEFAULT_BASE_URL) -> dict[str, int]:
    session = PoliteSession(base_url)
    conn = get_connection()
    try:
        return {city: crawl_city(city, session=session, conn=conn) for city in CITIES}
    finally:
        session.close()
        conn.close()


def main() -> int:
    counts = crawl_all_cities()
    for city, count in counts.items():
        print(f"{city}: {count} 列 daily_weather 寫入（含更新）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
