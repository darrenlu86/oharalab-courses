"""
設定層（config layer）——集中讀取所有環境變數，其他模組一律透過 `get_settings()`
取得設定值，不直接呼叫 `os.environ`。

跟 meowshop 教學範例的 config.py 是同一套設計，這裡不重複解釋每個決策，只講
跟上一份教材不一樣的地方：本階段只有 SQLite 一種資料庫（master spec 規定本課程
單一 SQLite、不用 supabase 套件），所以沒有 `db_backend` / `supabase_url` 這些欄位。

`get_settings()` 一樣刻意**不**用 `functools.lru_cache` 做成單例：測試（tests/conftest.py）
需要在同一個 Python process 裡用 `monkeypatch.setenv()` 把 `SQLITE_PATH` 換成每個測試
自己的暫存資料庫檔案，如果 Settings 被快取住，測試改了環境變數也不會生效。

## SECRET_KEY 沒設定時的安全警告

`DEFAULT_SECRET_KEY` 是刻意寫在課程原始碼裡、公開可見的字串，目的是讓學員不用
先申請/產生任何金鑰就能零設定跑起這支後端——這是教學上的刻意取捨，理由跟
`load_dotenv()` 找不到 `.env` 也不報錯是同一套精神。但正因為這個字串公開刊在
原始碼裡，任何人都看得到，如果直接把用預設值跑起來的服務部署到外部網址，
等於完全沒有登入驗證：攻擊者可以離線用同一把 key 簽出任意內容的 JWT
（包含偽造成 `role: admin` 的 token），不需要碰到伺服器一次就能通過
`app/deps.py` 的驗證。`is_default_secret_key()` / `warn_if_default_secret_key()`
拆成兩支函式方便個別單元測試：前者是純判斷邏輯，後者才是印警告的副作用，
測試不需要真的解析 stderr 就能驗證判斷是否正確（見 tests/test_config.py）。

警告只在應用程式啟動時印一次（見各 stage `app/main.py` 裡 `warn_if_default_secret_key
(settings.secret_key)` 這一行的呼叫點），刻意不是放進 `get_settings()` 本身——
`get_settings()` 沒有做成單例，`app/security.py` 的 `create_access_token()` /
`decode_access_token()` 幾乎每個請求都會呼叫一次，如果警告邏輯放在 `get_settings()`
裡，開發模式下沒設 `.env` 時，每一次登入、每一次需要驗證身分的 API 呼叫都會
在終端機再印一次同樣的警告，反而會把真正重要的訊息淹沒在洗版的重複輸出裡。
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# backend/ 目錄的絕對路徑（config.py 在 backend/app/config.py，往上兩層就是 backend/）。
BASE_DIR = Path(__file__).resolve().parent.parent

# 載入 backend/.env（檔案不存在也不會報錯，直接跳過）。
load_dotenv(BASE_DIR / ".env")

# 公開刊在原始碼裡的預設值——本機教學可用，對外部署等於沒有登入驗證，完整理由見
# 本檔開頭「SECRET_KEY 沒設定時的安全警告」一節。
DEFAULT_SECRET_KEY = "dev-secret-change-me"


@dataclass
class Settings:
    secret_key: str
    cors_origins: list[str]
    sqlite_path: Path


def is_default_secret_key(secret_key: str) -> bool:
    """判斷目前的 SECRET_KEY 是不是還停留在課程原始碼裡公開刊出的預設值。

    抽成獨立的純函式（沒有任何 I/O、不印任何東西），方便測試直接驗證判斷邏輯，
    不需要真的啟動一次 FastAPI app 或去解析 stderr 輸出內容。
    """
    return secret_key == DEFAULT_SECRET_KEY


def warn_if_default_secret_key(secret_key: str) -> None:
    """SECRET_KEY 仍是預設值時，在啟動階段對 stderr 印出醒目的多行警告。

    只警告、不擋下啟動：本機教學（不特別設 `.env` 直接 `uvicorn app.main:app`）
    仍然要能零設定跑起來，這是這門課的教學前提，跟 `load_dotenv()` 找不到 `.env`
    也不報錯是同一套設計精神；但「能在本機跑」不代表「能對外部署」——如果不印出
    這個警告，學員很容易在不知情的狀況下把用預設 key 跑起來的服務部署到公開網址。
    """
    if not is_default_secret_key(secret_key):
        return

    border = "=" * 70
    lines = [
        "",
        border,
        "[安全警告] SECRET_KEY 目前是預設值 dev-secret-change-me",
        border,
        "這個字串直接寫在課程原始碼裡，任何人只要看過原始碼就知道。",
        "",
        "本機開發、跟著教材操作可以放心使用；但如果把這支服務部署到外部網址",
        "（雲端主機、分享連結給同學或朋友連線），這個預設值等於完全沒有登入",
        "驗證——攻擊者可以離線用同一把 key 簽出任意內容的 JWT，包含偽造成",
        "管理員（role=admin）身分的 token，不需要真的登入就能通過驗證。",
        "",
        "正式部署前，請先在 backend/.env 設定一組隨機的 SECRET_KEY。",
        "可以用以下指令產生一組安全的隨機值（64 個十六進位字元）：",
        "",
        "    openssl rand -hex 32",
        "",
        "把產生出來的值貼到 backend/.env 的 SECRET_KEY= 後面即可，完整步驟見",
        "docs/DEPLOY.md「環境變數」一節。",
        border,
        "",
    ]
    print("\n".join(lines), file=sys.stderr)


def get_settings() -> Settings:
    secret_key = os.environ.get("SECRET_KEY", DEFAULT_SECRET_KEY)

    cors_raw = os.environ.get("CORS_ORIGINS", "*")
    cors_origins = ["*"] if cors_raw.strip() == "*" else [o.strip() for o in cors_raw.split(",") if o.strip()]

    sqlite_path_raw = os.environ.get("SQLITE_PATH", "data/brewgo.db")
    sqlite_path = Path(sqlite_path_raw)
    if not sqlite_path.is_absolute():
        # 統一轉成絕對路徑，避免受「目前工作目錄」影響——不管從哪個資料夾執行
        # uvicorn/pytest，都能正確找到同一個 SQLite 檔案。
        sqlite_path = BASE_DIR / sqlite_path

    return Settings(
        secret_key=secret_key,
        cors_origins=cors_origins,
        sqlite_path=sqlite_path,
    )
