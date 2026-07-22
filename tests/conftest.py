"""
tests/conftest.py — pytest 共用 fixture。

做什麼：
    提供 `repo` fixture：每個測試都會拿到一個「全新、獨立」的 SqliteRepository，
    背後接的是 pytest 自動建立的暫存目錄（tmp_path）裡的 SQLite 檔案，
    並已經執行過 db/schema_sqlite.sql 建好所有資料表。

為什麼這樣設計：
    - 用暫存檔案而不是真正的 data/tsmc.db：測試不該互相汙染，也不該汙染
      開發時累積的真實資料。每個測試函式結束後，pytest 會自動清掉
      tmp_path 底下的暫存檔案。
    - fixture 直接回傳 SqliteRepository 實例（而不是走 db.factory），
      是因為測試的目標就是「驗證 SqliteRepository 這個實作本身正不正確」，
      不需要透過 factory 的環境變數判斷邏輯繞一圈。
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

# 確保可以 import 到專案根目錄的 db / config 套件（pytest 從專案根目錄執行時
# 通常已經在 sys.path 裡，這裡多一道保險，避免不同執行方式下 import 失敗）。
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from db.sqlite_repo import SqliteRepository  # noqa: E402

SCHEMA_PATH = PROJECT_ROOT / "db" / "schema_sqlite.sql"


@pytest.fixture
def repo(tmp_path) -> SqliteRepository:
    """回傳一個已建表、乾淨的 SqliteRepository，資料庫檔案放在 pytest 暫存目錄。"""
    db_path = tmp_path / "test_tsmc.db"
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema_sql)
    return SqliteRepository(str(db_path))
