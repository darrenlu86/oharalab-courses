"""關卡三：直接打 JSON API——GET /api/latest?city= 取得近 30 天資料。

跟 crawl_records.py（解析 HTML 表格）拿到的是同一份底層資料，但走的是
結構化 JSON,不需要 BeautifulSoup。刻意跟 crawl_records.py 共用同一張
daily_weather 表與同一組 UNIQUE(city, date) 冪等鍵,示範「同一份資料可以
透過不同介面（HTML 或 JSON API）取得,寫進資料庫後兩條路徑互不打架」。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from stage3_crawler.crawler.crawl_records import API_TO_DB_COLUMN, CITIES  # noqa: E402
from stage3_crawler.crawler.db import get_connection, upsert_daily_weather  # noqa: E402
from stage3_crawler.crawler.http_client import PoliteSession  # noqa: E402

DEFAULT_BASE_URL = "http://127.0.0.1:8310"


def parse_latest_json(payload: list[dict]) -> list[dict]:
    """把 /api/latest 回應（API 欄名）轉成 daily_weather 表欄名（不含 city）。

    注意：sandbox_site 的 `/api/latest` 是直接把 CSV 讀進來的字串原樣塞進
    JSON（`sandbox_site/data.py` 的 `_load_weather` 沒有轉型),所以這裡收到
    的 `temperature_2m_max` 這類欄位其實是字串 `"25.4"` 而不是 JSON 數字。
    SQLite 的欄位型別親和性（type affinity）剛好會把這種字串自動轉成
    REAL/INTEGER,不轉型也「能動」——但那是隱性魔法,不是正確的程式碼,
    這裡刻意明確轉型,不依賴底層資料庫剛好幫你補洞。
    """
    rows = []
    for item in payload:
        row = {"date": item["date"]}
        for api_col, db_col in API_TO_DB_COLUMN.items():
            value = item.get(api_col)
            if value is None or value == "":
                row[db_col] = None
            elif db_col == "wind_dir":
                row[db_col] = int(float(value))
            else:
                row[db_col] = float(value)
        rows.append(row)
    return rows


def crawl_city(city: str, session: PoliteSession | None = None, base_url: str = DEFAULT_BASE_URL, conn=None) -> int:
    own_session = session is None
    if own_session:
        session = PoliteSession(base_url)
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    try:
        resp = session.get("/api/latest", params={"city": city})
        rows = parse_latest_json(resp.json())
        for row in rows:
            row["city"] = city
            upsert_daily_weather(conn, row)
        return len(rows)
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
        print(f"{city}: {count} 列近 30 天資料（JSON API 路徑，upsert 進 daily_weather）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
