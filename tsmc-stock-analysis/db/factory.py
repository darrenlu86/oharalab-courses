"""
db/factory.py — 依設定分派實際要使用的 repository 實作（工廠模式）。

做什麼：
    提供 `get_repository()`，讀取 config.DB_BACKEND，回傳對應的
    StockRepository 實作物件（SqliteRepository 或 SupabaseRepository）。

為什麼這樣設計：
    這是整個「資料庫可抽換」設計的關鍵接合點。爬蟲與 Dashboard 的程式碼裡
    只會出現 `from db.factory import get_repository` 這一行，完全不必知道
    也不必 import 任何具體實作類別。切換資料庫後端只需要改 .env 的
    DB_BACKEND，不用改一行呼叫端程式碼。

注意：
    - 型別標注寫成 `-> StockRepository`（回傳抽象介面型別），而不是
      `-> SqliteRepository`：呼叫端應該只依賴介面約定的方法，不該依賴
      特定實作才有的額外功能，這是物件導向設計中「依賴反轉」的具體示範。
"""

from __future__ import annotations

import config
from db.base import StockRepository
from db.sqlite_repo import SqliteRepository


def get_repository() -> StockRepository:
    """依 config.DB_BACKEND 回傳對應的 StockRepository 實作。

    DB_BACKEND=sqlite（預設）→ SqliteRepository（讀 config.SQLITE_PATH）
    DB_BACKEND=supabase      → SupabaseRepository（讀 config.SUPABASE_URL/KEY）

    注意：SupabaseRepository 只在真的選用 supabase 後端時才 import，
    避免沒裝好 supabase 套件、或沒填 Supabase 設定的環境（例如本專案的
    預設教學情境）在 import db.factory 這一步就意外出錯。
    """
    backend = config.DB_BACKEND

    if backend == "sqlite":
        return SqliteRepository(config.SQLITE_PATH)

    if backend == "supabase":
        from db.supabase_repo import SupabaseRepository

        return SupabaseRepository(config.SUPABASE_URL, config.SUPABASE_KEY)

    raise ValueError(
        f"不支援的 DB_BACKEND: {backend!r}（僅支援 'sqlite' 或 'supabase'）"
    )
