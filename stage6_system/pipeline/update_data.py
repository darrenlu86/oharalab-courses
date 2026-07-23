"""補最新一日天氣資料進 SQLite（`daily_weather` 表）。

用法：
    venv/bin/python -m stage6_system.pipeline.update_data              # 打 Open-Meteo archive API
    venv/bin/python -m stage6_system.pipeline.update_data --from-csv   # 離線：直接重灌 data/raw/*.csv

線上模式：對每個城市查資料庫裡目前最新的日期，從「隔天」補到「昨天」
（archive API 通常只到昨天為止有完整資料，今天的資料還在處理中）。
離線模式（`--from-csv`）不連網路，直接把 `data/raw/*.csv` 整批 upsert
一次——用在沒有網路的教學現場，或是 `bootstrap.py`／pytest 需要確保
資料庫有資料但不想真的打 API 的情境。
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from common.paths import RAW_DIR  # noqa: E402
from stage3_crawler.crawler.crawl_records import API_TO_DB_COLUMN, CITIES  # noqa: E402
from stage3_crawler.crawler.db import get_connection, upsert_daily_weather  # noqa: E402

ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"
CITY_COORDS = {
    "taipei": (25.0330, 121.5654),
    "taichung": (24.1477, 120.6736),
    "kaohsiung": (22.6273, 120.3014),
}
DAILY_VARS = list(API_TO_DB_COLUMN.keys())
TIMEOUT_SECONDS = 30.0


def _get_last_date(conn, city: str) -> date | None:
    row = conn.execute(
        "SELECT MAX(date) FROM daily_weather WHERE city = ?", (city,)
    ).fetchone()
    if row is None or row[0] is None:
        return None
    return date.fromisoformat(row[0])


def _row_from_api_item(date_str: str, daily: dict, i: int) -> dict:
    row = {"date": date_str}
    for api_col, db_col in API_TO_DB_COLUMN.items():
        value = daily[api_col][i]
        if value is None:
            row[db_col] = None
        elif db_col == "wind_dir":
            row[db_col] = int(value)
        else:
            row[db_col] = float(value)
    return row


def update_city_from_api(city: str, conn, session=None, today: date | None = None) -> int:
    """把某城市資料庫裡缺的天數（最新日期隔天 ~ 昨天）補進 daily_weather。

    回傳實際 upsert 的列數（0 代表已經是最新，不需要補）。
    """
    if session is None:
        session = requests
    today = today or date.today()
    yesterday = today - timedelta(days=1)

    last_date = _get_last_date(conn, city)
    start_date = (last_date + timedelta(days=1)) if last_date else yesterday - timedelta(days=29)

    if start_date > yesterday:
        return 0  # 已經是最新，不需要打 API

    lat, lon = CITY_COORDS[city]
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date.isoformat(),
        "end_date": yesterday.isoformat(),
        "daily": ",".join(DAILY_VARS),
        "timezone": "Asia/Taipei",
    }
    resp = session.get(ARCHIVE_API_URL, params=params, timeout=TIMEOUT_SECONDS)
    resp.raise_for_status()
    payload = resp.json()
    daily = payload["daily"]

    count = 0
    for i, date_str in enumerate(daily["time"]):
        row = _row_from_api_item(date_str, daily, i)
        row["city"] = city
        upsert_daily_weather(conn, row)
        count += 1
    return count


def update_from_api(cities: list[str] = CITIES, conn=None, session=None) -> dict[str, int]:
    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    try:
        return {city: update_city_from_api(city, conn, session=session) for city in cities}
    finally:
        if own_conn:
            conn.close()


def update_city_from_csv(city: str, conn, raw_dir: Path = RAW_DIR) -> int:
    csv_path = raw_dir / f"{city}.csv"
    count = 0
    with csv_path.open(newline="", encoding="utf-8") as f:
        for raw_row in csv.DictReader(f):
            row = {"date": raw_row["date"], "city": city}
            for api_col, db_col in API_TO_DB_COLUMN.items():
                value = raw_row.get(api_col, "")
                row[db_col] = float(value) if value not in ("", None) else None
                if db_col == "wind_dir" and row[db_col] is not None:
                    row[db_col] = int(row[db_col])
            upsert_daily_weather(conn, row)
            count += 1
    return count


def update_from_csv(cities: list[str] = CITIES, raw_dir: Path = RAW_DIR, conn=None) -> dict[str, int]:
    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    try:
        return {city: update_city_from_csv(city, conn, raw_dir=raw_dir) for city in cities}
    finally:
        if own_conn:
            conn.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="補最新天氣資料進 data/weather_course.db")
    parser.add_argument("--from-csv", action="store_true", help="離線模式：直接重灌 data/raw/*.csv，不打 API")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.from_csv:
        print("離線模式：從 data/raw/*.csv 重新匯入...")
        counts = update_from_csv()
    else:
        print("線上模式：查詢 Open-Meteo archive API 補最新資料...")
        counts = update_from_api()
    for city, count in counts.items():
        if count:
            print(f"  {city}: 補了 {count} 天")
        else:
            print(f"  {city}: 已是最新，不需要補")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
