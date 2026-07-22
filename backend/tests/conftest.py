"""
pytest 共用 fixture——讓每個測試都在自己專屬的暫存 SQLite 資料庫上執行，測試之間互不干擾。

關鍵設計「為什麼」：
- 用 pytest 內建的 `tmp_path`（每個測試函式各自獨立、跑完自動清掉的暫存資料夾）
  當作 SQLite 檔案位置，搭配 `monkeypatch.setenv()` 把 `SQLITE_PATH` / `DB_BACKEND`
  指過去——這樣完全不會動到專案真正的 `backend/data/meowshop.db`。
- `app.config.get_settings()` 刻意設計成「每次呼叫都重新讀 os.environ」
  （詳見 app/config.py 的說明），所以這裡只要在測試一開始 monkeypatch.setenv，
  接下來這個測試函式送出的每一個 API request，都會讀到指向暫存資料庫的設定，
  不需要重新 import 整個 app 模組、也不會有測試互相污染同一顆資料庫的問題。
"""

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = BACKEND_DIR / "app" / "db" / "sqlite_schema.sql"
SEED_PATH = BACKEND_DIR / "app" / "db" / "seed_products.json"


@pytest.fixture
def db_path(tmp_path, monkeypatch) -> Path:
    """準備一個乾淨的暫存 SQLite 資料庫（已建表 + 已匯入 10 筆種子商品），並切換環境變數指過去。"""
    path = tmp_path / "test.db"
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(path))
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")

    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()

        seed_products = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        for product in seed_products:
            conn.execute(
                """
                INSERT INTO products
                    (name, description, price, stock, category, image_url, is_active)
                VALUES
                    (:name, :description, :price, :stock, :category, :image_url, :is_active)
                """,
                product,
            )
        conn.commit()
    finally:
        conn.close()

    return path


@pytest.fixture
def client(db_path) -> TestClient:
    """回傳一個綁定在暫存資料庫上的 TestClient。

    注意：`from app.main import app` 特意寫在 fixture 內部（而不是檔案最上面），
    確保執行到這一行的時候，上面的 `db_path` fixture 已經先把環境變數設定好了。
    """
    from app.main import app

    return TestClient(app)


@pytest.fixture
def register_and_login(client: TestClient):
    """回傳一個小工具函式：註冊 + 登入一個測試帳號，並回傳可以直接用的 Authorization header。"""

    def _make(email: str = "tester@example.com", password: str = "password123", name: str = "測試貓奴"):
        client.post(
            "/api/auth/register",
            json={"email": email, "password": password, "name": name},
        )
        resp = client.post("/api/auth/login", json={"email": email, "password": password})
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture
def auth_headers(register_and_login):
    """預設測試帳號的 Authorization header（大部分測試只需要「隨便一個登入使用者」）。"""
    return register_and_login()
