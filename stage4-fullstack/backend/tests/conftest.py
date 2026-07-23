"""
pytest 共用 fixture——讓每個測試都在自己專屬的暫存 SQLite 資料庫上執行，測試之間互不干擾。

跟 meowshop 的 conftest.py 同一套設計：用 pytest 內建的 `tmp_path`（每個測試函式
各自獨立、跑完自動清掉的暫存資料夾）當作 SQLite 檔案位置，搭配 `monkeypatch.setenv()`
把 `SQLITE_PATH` 指過去。`app.config.get_settings()` 刻意每次呼叫都重新讀
`os.environ`（見 app/config.py 的說明），所以這裡只要在測試一開始 monkeypatch，
接下來這個測試函式送出的每一個 request 都會讀到指向暫存資料庫的設定。
"""

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
SEED_PATH = BACKEND_DIR / "app" / "db" / "seed_products.json"


@pytest.fixture
def db_path(tmp_path, monkeypatch) -> Path:
    """準備一個乾淨的暫存 SQLite 資料庫（已建表 + 已匯入 12 筆種子商品），並切換環境變數指過去。"""
    path = tmp_path / "test.db"
    monkeypatch.setenv("SQLITE_PATH", str(path))
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")

    # 這裡故意不 import app.db.database.init_schema，直接用 sqlite3 標準庫執行同一份
    # schema.sql——避免測試 fixture 跟被測程式碼共用同一支「建表」函式，如果那支
    # 函式本身寫錯，測試會用同一個錯誤的版本蓋掉自己，反而測不出問題。
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        schema_sql = (BACKEND_DIR / "app" / "db" / "schema.sql").read_text(encoding="utf-8")
        conn.executescript(schema_sql)
        conn.commit()

        seed_products = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        for product in seed_products:
            conn.execute(
                """
                INSERT INTO products (id, name, description, price, stock, category, image_url)
                VALUES (:id, :name, :description, :price, :stock, :category, :image_url)
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

    `from app.main import app` 特意寫在 fixture 內部（而不是檔案最上面），確保
    執行到這一行時，上面的 `db_path` fixture 已經先把環境變數設定好了。
    """
    from app.main import app

    return TestClient(app)


@pytest.fixture
def register_and_login(client: TestClient):
    """回傳一個小工具函式：註冊 + 登入一個測試帳號，並回傳可以直接用的 Authorization header。"""

    def _make(email: str = "tester@example.com", password: str = "password123", name: str = "測試客人"):
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
