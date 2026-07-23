"""
scripts/init_db.py — 初始化資料庫：建表＋種入台積電基本資料（seed data）。

做什麼：
    1. 讀取 db/schema_sqlite.sql，在 config.SQLITE_PATH 指定的 SQLite 檔案
       建立所有資料表（若已存在則略過，因為 schema 用 CREATE TABLE IF NOT EXISTS）。
    2. 透過 db.factory.get_repository() 呼叫 upsert_stock()，種入台積電
       （2330）的基本資料，讓後續三支爬蟲一啟動就有 stocks 表可以參照
       （daily_prices / news / supply_chain_companies 都有 FOREIGN KEY 指到
       stocks(symbol)）。

為什麼這樣設計：
    建表用「直接執行 .sql 檔」而不是在 Python 裡寫一堆 CREATE TABLE 字串，
    是因為 schema 定義本身就該是純 SQL——這樣 schema_sqlite.sql 也可以單獨
    被學員閱讀、甚至直接用 sqlite3 CLI 手動執行，不必透過這支腳本。
    seed 資料則透過 repository 介面寫入（呼叫 upsert_stock()），而不是
    直接寫 SQL INSERT——示範「就算是初始化腳本，也應該走同一套資料存取層」，
    避免以後 schema 或去重邏輯改了，這裡卻忘記跟著改。

    SQLite 檔案路徑一律沿用 config.SQLITE_PATH（已在 config.py 內 resolve
    成絕對路徑），不在本腳本自己再組一次路徑——避免兩處各自組合路徑的邏輯
    分岔（例如一處用 PROJECT_ROOT 相對組合、一處用別的基準），日後其中一處
    改了卻忘記同步另一處。

使用方式：
    venv/bin/python scripts/init_db.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# 讓本腳本可以在專案根目錄外的位置被執行時，仍然找得到 config / db 套件。
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
from crawlers.common import setup_logging  # noqa: E402
from db.factory import get_repository  # noqa: E402

SCHEMA_PATH = PROJECT_ROOT / "db" / "schema_sqlite.sql"

logger = setup_logging("init_db")


def _has_legacy_schema(sqlite_path: Path) -> bool:
    """偵測既有 db 檔是否為舊版 schema（supply_chain_companies.segment 仍允許 NULL）。

    為什麼要偵測（教學重點）：
        `CREATE TABLE IF NOT EXISTS` 遇到已經存在的資料表不會做任何事，
        也就是不會幫忙把舊表的欄位約束改成新版（例如 segment 從允許 NULL
        改成 NOT NULL DEFAULT ''）。如果學員手上的 data/tsmc.db 是用舊版
        schema 建的，直接重跑本腳本並「看起來」執行成功，但 UNIQUE 去重
        失效的問題其實完全沒被修好——這種「有跑但沒生效」的沉默失敗，
        對初學者來說最難排查。
        本專案刻意不做自動 migration（欄位型別轉換、既有 NULL 值要補成
        什麼、風險評估……這些對教學專案來說太複雜也太危險），改成清楚
        偵測並提示學員手動處理，行為透明可預期。
    """
    if not sqlite_path.exists():
        return False
    with sqlite3.connect(sqlite_path) as conn:
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name = 'supply_chain_companies'"
        ).fetchone()
        if table_exists is None:
            return False
        # PRAGMA table_info 每一列是 (cid, name, type, notnull, dflt_value, pk)；
        # notnull == 0 代表該欄位目前還允許 NULL，也就是舊版 schema。
        columns = conn.execute("PRAGMA table_info(supply_chain_companies)").fetchall()
        for column in columns:
            if column[1] == "segment":
                return column[3] == 0
    return False


def create_tables() -> None:
    """執行 db/schema_sqlite.sql，建立所有資料表。

    若偵測到既有 db 檔是舊版 schema，不會靜默嘗試 migrate，而是直接中止
    並提示學員手動刪除（建議先備份）後重新執行。
    """
    sqlite_path = Path(config.SQLITE_PATH)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    if _has_legacy_schema(sqlite_path):
        logger.error(
            "偵測到 %s 是舊版 schema（supply_chain_companies.segment 仍允許 "
            "NULL，UNIQUE 去重會失效）。本腳本不會自動 migrate，請手動處理："
            "1) 先備份：mv %s %s.bak-<今天日期>；"
            "2) 刪除原檔後重新執行 `venv/bin/python scripts/init_db.py` "
            "建立新 schema；3) 之後重跑爬蟲（scripts/run_all_crawlers.py）"
            "回填資料。",
            sqlite_path,
            sqlite_path,
            sqlite_path,
        )
        raise SystemExit(1)

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with sqlite3.connect(sqlite_path) as conn:
        # executescript 可以一次執行多條由分號分隔的 SQL 語句，
        # 建表這種一次性批次操作很適合，不用逐條 execute()。
        conn.executescript(schema_sql)
    logger.info("資料表已建立於：%s", sqlite_path)


def seed_stocks() -> None:
    """種入教學專案的目標股票：台積電（2330）。"""
    repo = get_repository()
    repo.upsert_stock(
        symbol="2330",
        name="台積電",
        market="上市",
        industry="半導體",
    )
    logger.info("已種入股票基本資料：2330 台積電（上市／半導體）")


def main() -> None:
    if config.DB_BACKEND != "sqlite":
        # 注意：本腳本目前只處理 SQLite 建表（執行 schema_sqlite.sql）。
        # 若 DB_BACKEND=supabase，請改到 Supabase SQL Editor 手動執行
        # db/schema_supabase.sql 建表，再執行本腳本種 seed 資料即可
        # （seed_stocks() 一樣會透過 get_repository() 走到 SupabaseRepository）。
        logger.info(
            "目前 DB_BACKEND=%r，略過 SQLite 建表步驟，僅執行 seed。",
            config.DB_BACKEND,
        )
    else:
        create_tables()

    seed_stocks()


if __name__ == "__main__":
    main()
