"""爬蟲寫入 SQLite 的共用層：連線建立（沿用 scripts/init_db.py 的 schema）
與四張表各自的 upsert 函式。

刻意示範兩種不同的冪等寫法：
- `upsert_station`/`upsert_comment`/`upsert_announcement` 用
  `INSERT OR IGNORE`——衝突時保留舊資料,不覆寫（適合「這筆資料本質上
  不會變」的情境,例如合成留言內容是固定生成的)。
- `upsert_daily_weather` 用 `INSERT ... ON CONFLICT DO UPDATE`——衝突時
  用新值覆寫舊值（適合「同一天的觀測值未來可能被來源修正」的情境,例如
  API 事後回補資料)。

兩種都能達成「重跑不會製造重複列」的冪等性,差別在「衝突時要不要更新」,
這是 SPEC §3.3 特別點名的教學案例（UNIQUE 鍵冪等 upsert),兩種寫法都值得
認識。
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from common.paths import DB_PATH  # noqa: E402
from scripts.init_db import build_database  # noqa: E402


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """回傳一個資料庫連線,確保表格與預設測站都已存在。

    `build_database` 本身是冪等的（`CREATE TABLE IF NOT EXISTS` +
    `INSERT OR IGNORE`），不管資料庫檔案存不存在都可以直接呼叫，不用
    在這裡自己判斷檔案存在與否（沿用 scripts/init_db.py 的 schema,
    不在這裡另外定義一份 SQL,避免兩邊 schema 漂移)。
    """
    build_database(db_path)
    return sqlite3.connect(db_path)


def upsert_station(conn: sqlite3.Connection, city: str, name_zh: str, latitude: float, longitude: float) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO stations (city, name_zh, latitude, longitude) VALUES (?, ?, ?, ?)",
        (city, name_zh, latitude, longitude),
    )
    conn.commit()


def upsert_daily_weather(conn: sqlite3.Connection, row: dict) -> None:
    """row 需含 city/date/temp_max/temp_min/temp_mean/precipitation_mm/
    rain_mm/precip_hours/windspeed_max/windgusts_max/wind_dir/radiation。
    衝突（同 city+date）時用新值覆寫舊值（見 module docstring）。
    """
    conn.execute(
        """
        INSERT INTO daily_weather
            (city, date, temp_max, temp_min, temp_mean, precipitation_mm, rain_mm,
             precip_hours, windspeed_max, windgusts_max, wind_dir, radiation)
        VALUES (:city, :date, :temp_max, :temp_min, :temp_mean, :precipitation_mm, :rain_mm,
                :precip_hours, :windspeed_max, :windgusts_max, :wind_dir, :radiation)
        ON CONFLICT(city, date) DO UPDATE SET
            temp_max=excluded.temp_max, temp_min=excluded.temp_min, temp_mean=excluded.temp_mean,
            precipitation_mm=excluded.precipitation_mm, rain_mm=excluded.rain_mm,
            precip_hours=excluded.precip_hours, windspeed_max=excluded.windspeed_max,
            windgusts_max=excluded.windgusts_max, wind_dir=excluded.wind_dir, radiation=excluded.radiation
        """,
        row,
    )
    conn.commit()


def upsert_comment(conn: sqlite3.Connection, comment_key: str, city: str, date: str, rating: int, content: str, crawled_at: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO comments (comment_key, city, date, rating, content, crawled_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (comment_key, city, date, rating, content, crawled_at),
    )
    conn.commit()


def upsert_announcement(conn: sqlite3.Connection, ann_key: str, title: str, body: str, published_at: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO announcements (ann_key, title, body, published_at) VALUES (?, ?, ?, ?)",
        (ann_key, title, body, published_at),
    )
    conn.commit()


def table_row_counts(conn: sqlite3.Connection) -> dict[str, int]:
    tables = ["stations", "daily_weather", "comments", "announcements", "predictions"]
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
