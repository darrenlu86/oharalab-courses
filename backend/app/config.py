"""
設定層（config layer）。

負責什麼：集中讀取所有環境變數（DB_BACKEND、SECRET_KEY、SUPABASE_URL、SUPABASE_KEY、
CORS_ORIGINS、SQLITE_PATH），其他模組一律透過 `get_settings()` 取得設定值，
不直接呼叫 `os.environ`——這樣以後要加新設定、或要換成別的設定來源（例如雲端的
Secret Manager），只需要改這一個檔案。

關鍵設計「為什麼」：
`get_settings()` 刻意**不**用 `functools.lru_cache` 做成單例，而是每次呼叫都重新讀一次
`os.environ`。原因是本專案的測試（tests/conftest.py）需要在同一個 Python process 裡，
用 `monkeypatch.setenv()` 把 `DB_BACKEND` / `SQLITE_PATH` 切換成每個測試自己的暫存
SQLite 檔案。如果 Settings 被快取成單例，測試改了環境變數也不會生效，會變成所有測試
共用同一顆資料庫、互相污染資料。這裡用「每次重讀」換取「測試好寫」，對教學專案來說
這點效能成本可以忽略。

注意：`load_dotenv()` 預設不會覆蓋「已經存在」的環境變數（override=False），
所以 pytest 用 monkeypatch 設的值永遠優先於 `.env` 檔案內容。
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# backend/ 目錄的絕對路徑（config.py 在 backend/app/config.py，往上兩層就是 backend/）。
# 用 __file__ 推算絕對路徑，而不是寫死字串或依賴「目前在哪個資料夾執行指令」，
# 這樣不管你從哪個工作目錄啟動程式，都能正確找到 backend/.env 與 SQLite 檔案。
BASE_DIR = Path(__file__).resolve().parent.parent

# 載入 backend/.env（如果檔案不存在，load_dotenv 不會報錯，直接跳過）。
load_dotenv(BASE_DIR / ".env")


@dataclass
class Settings:
    """一次讀取好的設定值集合。"""

    db_backend: str
    secret_key: str
    supabase_url: str
    supabase_key: str
    cors_origins: list[str]
    sqlite_path: Path


def get_settings() -> Settings:
    """讀取目前的環境變數，回傳一份 Settings。"""
    db_backend = os.environ.get("DB_BACKEND", "sqlite")
    secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_KEY", "")

    cors_raw = os.environ.get("CORS_ORIGINS", "*")
    # 注意：CORS_ORIGINS="*" 代表「全部允許」，這時不能把它 split(",") 變成 ["*"]
    # 以外的東西處理錯——這裡明確判斷 "*" 這個特殊值，其餘才用逗號切開多個網址。
    cors_origins = ["*"] if cors_raw.strip() == "*" else [o.strip() for o in cors_raw.split(",") if o.strip()]

    sqlite_path_raw = os.environ.get("SQLITE_PATH", "data/meowshop.db")
    sqlite_path = Path(sqlite_path_raw)
    if not sqlite_path.is_absolute():
        # SQLITE_PATH 在 .env.example 裡註明是「相對 backend/ 目錄」，
        # 所以這裡統一轉成絕對路徑，避免又受「目前工作目錄」影響。
        sqlite_path = BASE_DIR / sqlite_path

    return Settings(
        db_backend=db_backend,
        secret_key=secret_key,
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        cors_origins=cors_origins,
        sqlite_path=sqlite_path,
    )
