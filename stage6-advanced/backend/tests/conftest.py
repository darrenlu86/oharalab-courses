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


@pytest.fixture(autouse=True)
def _reset_products_cache():
    """stage6 新增：`app.cache.products_cache`（見 app/cache.py）是模組層級的
    process 內單例，會在整個 pytest 執行期間一直存活——如果不主動清空，測試 A
    在它自己的暫存資料庫查出來的商品列表會被快取住，測試 B 換了一個全新的
    暫存資料庫，卻可能因為 cache key（`(category, search)`）剛好相同，讀到
    測試 A 遺留下來的快取內容，兩個測試看起來各自獨立、實際上會互相汙染。
    這是 in-memory 快取「跟測試隔離設計」互相打架的真實案例，`autouse=True`
    確保每一個測試函式開始前都先清空一次，不用每個測試檔自己記得呼叫。
    """
    from app.cache import products_cache

    products_cache.invalidate_all()
    yield
    products_cache.invalidate_all()


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


@pytest.fixture
def admin_headers(client: TestClient, db_path) -> dict:
    """建立一個 role='admin' 的帳號並登入，回傳可直接用的 Authorization header。

    stage5 新增：`POST /api/auth/register` 這個公開端點永遠只會建立 'customer'
    角色的帳號（見 app/routers/auth.py），這是刻意設計——不可能有人靠著自己填
    註冊表單就變成管理員。測試需要 admin 帳號時，只能像這裡一樣直接在資料庫層
    插入一筆 role='admin' 的使用者，這也順便驗證了「一般註冊流程做不到這件事」
    這個安全邊界本身。
    """
    import sqlite3

    from app.security import hash_password

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO users (email, password_hash, name, role) VALUES (?, ?, ?, 'admin')",
        ("admin-test@example.com", hash_password("AdminPass123"), "測試管理員"),
    )
    conn.commit()
    conn.close()

    resp = client.post(
        "/api/auth/login", json={"email": "admin-test@example.com", "password": "AdminPass123"}
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
