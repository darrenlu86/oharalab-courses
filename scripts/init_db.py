"""建立 SQLite 資料庫（data/weather_course.db）並匯入預設測站資料。

預設行為：如果資料庫檔案已經存在，直接印訊息並結束，不會動到既有資料
（教學情境常常是學員已經跑過爬蟲、資料庫裡已經有東西，不應該無聲無息
被清掉）。要重建資料庫，必須顯式加 --reset，這時候會先把舊檔案備份成
weather_course.db.bak-YYYYMMDD，再刪除重建。

用法：
    venv/bin/python scripts/init_db.py            # 首次建立，或確認已存在就不動
    venv/bin/python scripts/init_db.py --reset     # 備份舊檔＋清空重建
"""

import argparse
import shutil
import sqlite3
import sys
from datetime import date
from pathlib import Path

# 讓這支腳本可以直接用 `python scripts/init_db.py` 執行（此時 repo 根不在
# sys.path 上），也能被 tests/conftest.py 當成一般模組 import。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.paths import DB_PATH  # noqa: E402（需先調整 sys.path 才能 import）

# SPEC §3.3 schema：五張表。獨立成常數並抽成 create_schema() 函式，
# 方便 tests/conftest.py 的 fresh_db fixture 直接複用建表邏輯，
# 不用在測試裡重貼一份 SQL（貼兩份遲早會兜不起來）。
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS stations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  city TEXT NOT NULL UNIQUE,          -- taipei / taichung / kaohsiung
  name_zh TEXT NOT NULL,              -- 台北 / 台中 / 高雄
  latitude REAL NOT NULL, longitude REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS daily_weather (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  city TEXT NOT NULL, date TEXT NOT NULL,        -- 'YYYY-MM-DD'
  temp_max REAL, temp_min REAL, temp_mean REAL,
  precipitation_mm REAL, rain_mm REAL, precip_hours REAL,
  windspeed_max REAL, windgusts_max REAL, wind_dir INTEGER, radiation REAL,
  UNIQUE(city, date)                              -- 冪等 upsert 鍵
);
CREATE TABLE IF NOT EXISTS comments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  comment_key TEXT NOT NULL UNIQUE,               -- 沙盒站上的 comment_id
  city TEXT NOT NULL, date TEXT NOT NULL,
  rating INTEGER NOT NULL, content TEXT NOT NULL,
  crawled_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS announcements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ann_key TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL, body TEXT NOT NULL, published_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS predictions (            -- stage6 監測用
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  city TEXT NOT NULL, target_date TEXT NOT NULL,
  rain_prob REAL NOT NULL, predicted_label INTEGER NOT NULL,
  actual_precip_mm REAL, actual_label INTEGER,      -- 回填前為 NULL
  model_version TEXT NOT NULL, created_at TEXT NOT NULL,
  UNIQUE(city, target_date, model_version)
);
"""

# 課程固定的三個測站
DEFAULT_STATIONS = [
    ("taipei", "台北", 25.0330, 121.5654),
    ("taichung", "台中", 24.1477, 120.6736),
    ("kaohsiung", "高雄", 22.6273, 120.3014),
]


def create_schema(conn: sqlite3.Connection) -> None:
    """在傳入的連線上建立 SPEC §3.3 的五張表（IF NOT EXISTS，可重複呼叫）。"""
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def insert_default_stations(conn: sqlite3.Connection) -> None:
    """匯入三個預設測站，用 INSERT OR IGNORE 保持冪等（重跑不會報錯或重複插入）。"""
    conn.executemany(
        "INSERT OR IGNORE INTO stations (city, name_zh, latitude, longitude) "
        "VALUES (?, ?, ?, ?)",
        DEFAULT_STATIONS,
    )
    conn.commit()


def build_database(db_path: Path) -> None:
    """在指定路徑上建立資料庫、建表、匯入測站。給 init_db() 與測試 fixture 共用，
    是本檔唯一真正動資料庫的地方。
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        create_schema(conn)
        insert_default_stations(conn)
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH, reset: bool = False) -> None:
    """建立資料庫；預設不動已存在的檔案，--reset 才備份既有檔案並刪除重建。"""
    if db_path.exists():
        if not reset:
            print(f"資料庫已存在：{db_path}，不重建（如需重建請加 --reset）。")
            return
        backup_path = db_path.with_name(
            f"{db_path.name}.bak-{date.today().strftime('%Y%m%d')}"
        )
        shutil.copy2(db_path, backup_path)
        print(f"--reset：已備份既有資料庫至 {backup_path}，接著刪除重建。")
        db_path.unlink()

    build_database(db_path)
    print(f"資料庫建立完成：{db_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="建立 data/weather_course.db 並匯入預設測站資料。"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="若資料庫已存在，先備份成 .bak-YYYYMMDD 再刪除重建（預設不重建）。",
    )
    args = parser.parse_args()
    init_db(reset=args.reset)


if __name__ == "__main__":
    main()
