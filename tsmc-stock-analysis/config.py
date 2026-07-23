"""
config.py — 全域設定讀取模組。

做什麼：
    用 python-dotenv 讀取專案根目錄的 .env 檔（若不存在則沿用系統環境變數的預設值），
    集中提供其他模組（db/、crawlers/、dashboard/）所需的設定常數。

為什麼這樣設計：
    教學重點之一是「設定與程式碼分離」——資料庫要接 SQLite 還是 Supabase、
    SQLite 檔案放哪裡，都不該寫死在程式裡，而是透過環境變數切換。
    這樣同一份程式碼可以在不同環境（本機開發、雲端部署）直接套用不同設定，
    也避免把機密（如 SUPABASE_KEY）寫進版本控制。

注意：
    - .env 檔本身已被 .gitignore 排除，不會被 commit；.env.example 才是公開範本。
    - load_dotenv() 找不到 .env 檔時不會報錯，只是安靜地跳過，此時所有設定都會落回下方預設值。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# 載入專案根目錄的 .env（若存在）。override=False：已存在的系統環境變數優先，
# 方便部署時直接用環境變數覆蓋，而不用改檔案。
load_dotenv(override=False)

# --- 資料庫後端選擇 ---
# sqlite（預設，教學與驗證用）｜ supabase（雲端選項，本專案不實際串接）
DB_BACKEND: str = os.getenv("DB_BACKEND", "sqlite")

# --- SQLite 設定 ---
# PROJECT_ROOT：以本檔案（config.py）所在目錄為基準，因為 config.py 固定放在
# 專案根目錄。
#
# 為什麼要把 SQLITE_PATH 鎖定在專案根目錄（初學者常踩的坑）：
#   .env 裡的 SQLITE_PATH 預設是相對路徑 "data/tsmc.db"。相對路徑「相對於
#   誰」取決於程式執行當下的工作目錄（cwd），不是這支程式檔案的位置。
#   如果只是單純 `os.getenv("SQLITE_PATH", ...)` 存成相對路徑字串，
#   同一份設定在專案根目錄執行 `python scripts/init_db.py` 是一份 db 檔，
#   換成先 `cd scripts/` 再執行，就會在 scripts/data/tsmc.db 生出第二份、
#   完全空白的 db 檔——兩邊資料對不起來，卻不會有任何錯誤訊息，非常難查。
#   解法是在這裡就把相對路徑 resolve 成絕對路徑（以 PROJECT_ROOT 為基準），
#   之後不管從哪個目錄呼叫 get_repository()，拿到的都是同一個 db 檔案。
PROJECT_ROOT: Path = Path(__file__).resolve().parent
_sqlite_path_raw = os.getenv("SQLITE_PATH", "data/tsmc.db")
_sqlite_path = Path(_sqlite_path_raw)
SQLITE_PATH: str = str(
    _sqlite_path if _sqlite_path.is_absolute() else PROJECT_ROOT / _sqlite_path
)

# --- Supabase 設定（DB_BACKEND=supabase 時才需要）---
SUPABASE_URL: str | None = os.getenv("SUPABASE_URL") or None
SUPABASE_KEY: str | None = os.getenv("SUPABASE_KEY") or None
