# DEVELOPMENT.md — 開發者/接手指南

這份文件給要接手擴充 MeowShop 的人看（不管是真人開發者還是 AI），假設你已經照 [`README.md`](README.md) 把專案跑起來過，也大致看過 [`docs/PRD.md`](docs/PRD.md) 的 API 規格與 ER 圖。這裡講的是「程式碼怎麼組織」與「要新增功能時，該從哪裡下手、依序改哪幾個檔案」。

## 1. 分層架構：Router → Repository 兩層設計

後端只有兩層，職責切得很乾淨：

```
HTTP 請求
   │
   ▼
Router 層（app/routers/*.py）
  - 解析 request（Pydantic model 自動驗證格式）
  - 呼叫 Repository 的方法做「拿資料/存資料」
  - 決定錯誤要回什麼狀態碼與訊息（404/409/401...）
  - 組成 response model 回傳
   │
   ▼
Repository 層（app/repositories/*.py）
  - 只知道「怎麼把資料存進去、怎麼把資料撈出來」
  - 回傳 plain dict，不知道 HTTP、不知道狀態碼是什麼
  - 有兩種實作：SQLite 版／Supabase 版，靠抽象介面（base.py）保證行為一致
```

**為什麼只切兩層，不切三層（例如再加一層 Service/商業邏輯層）**：這是教學專案，刻意保持簡單——目前的商業邏輯（例如「庫存夠不夠」「訂單狀態能不能轉換」）份量還不大，直接寫在 router 函式裡就看得懂，硬加一層 Service 只會讓學員多一層要理解的抽象，卻沒有對應的好處。如果之後功能變複雜（例如同一段邏輯被兩支不同 API 重複用到、或商業規則牽涉到好幾個 Repository 才能算完），那時候再抽出一個 Service 層是合理的重構方向，屬於本文件最後「可擴充方向」清單的一項。

**為什麼 Router 依賴「抽象介面」而不是直接依賴 SQLite 或 Supabase 的實作**：`app/repositories/base.py` 用 Python 的 `ABC`（抽象基底類別）定義了每一種 Repository「必須要有哪些方法、參數與回傳型別」，但完全不寫「怎麼存」。Router 只 import `base.py` 定義的型別做型別標註，實際注入的是哪個實作，由 `app/deps.py` 的 `get_repos()`（背後呼叫 `app/repositories/factory.py` 的 `get_repositories()`）依 `DB_BACKEND` 環境變數決定。好處：

1. **換資料庫不用改 router 一行程式碼**——`DB_BACKEND=sqlite` 換成 `DB_BACKEND=supabase`，routers 完全無感。
2. **測試好寫**——`tests/conftest.py` 只要把環境變數指向暫存的 SQLite 檔案，就能用「真的」`SQLiteUserRepository` 之類的實作測試，不需要 mock 掉整個資料庫。
3. **依賴方向正確**——「高層模組（router）依賴抽象、不依賴細節」，這是很多正式後端框架都會用的 Repository Pattern，提早建立這個習慣，之後接觸更大型系統會更容易上手。

## 2. 資料夾用途一覽

```
backend/
├── requirements.txt        套件清單（版本區間釘住，見 README 環境需求）
├── .env.example             環境變數範本（複製成 .env 使用，.env 本身不進版控）
├── app/
│   ├── main.py               組裝點：建立 FastAPI app、掛 CORS、註冊 routers、掛前端靜態檔
│   ├── config.py             讀環境變數，統一用 get_settings() 取值（見第 7 節程式碼慣例）
│   ├── security.py           bcrypt 雜湊/驗證、JWT 簽發/解碼
│   ├── schemas.py            全部 Pydantic request/response models
│   ├── deps.py                FastAPI 依賴：get_repos()、get_current_user()
│   ├── routers/                每個檔案對應一組 API 前綴（/api/auth、/api/products...）
│   ├── repositories/
│   │   ├── base.py             抽象介面（ABC）＋ DuplicateEmailError
│   │   ├── factory.py          依 DB_BACKEND 組裝出一組 Repos
│   │   ├── sqlite_repo.py      SQLite 實作（本機開發預設）
│   │   └── supabase_repo.py    Supabase 實作
│   └── db/
│       ├── sqlite_schema.sql     SQLite 建表語法
│       ├── supabase_schema.sql   PostgreSQL 建表語法（欄位名稱與上面完全對齊）
│       └── seed_products.json    10 筆種子商品資料
├── scripts/
│   └── init_db.py            建表 + 匯入種子資料（--reset 才會清空重建，見 README 第 7 節）
├── data/                     SQLite 檔案實際存放處（.gitignore 排除，只留 .gitkeep 佔位）
└── tests/
    ├── conftest.py            共用 fixture（見第 6 節）
    └── test_*.py              一個模組一支測試檔

frontend/
├── *.html                    每個頁面一個檔案，沒有 build step，直接是最終產物
├── css/style.css             單一樣式檔，全站共用
├── js/
│   ├── api.js                唯一的 fetch 封裝層（baseURL、帶 token、統一錯誤處理）
│   ├── auth.js                token 存取（localStorage）、登入狀態判斷
│   ├── ui.js                  共用元件：navbar/footer 注入、toast 提示、金額格式化
│   └── pages/*.js              每個頁面各自的邏輯，只處理該頁面的 DOM 與 API 呼叫
└── images/                    logo、hero 插圖、每個商品一張 SVG（p1.svg ~ p10.svg）
```

## 3. 資料存取層怎麼擴充——以「加入收藏清單（wishlist）」為例

假設你要加一個「收藏商品」功能。整個過程完全不用碰 router 現有的檔案，也不用改 `deps.py`；只需要照下面順序動手：

### 3.1 先在 `base.py` 定義抽象介面

```python
# app/repositories/base.py（新增一個 class，放在既有幾個 Repository 後面）

class WishlistRepository(ABC):
    """收藏清單資料存取介面。"""

    @abstractmethod
    def list_items(self, user_id: int) -> list[dict]:
        """列出某使用者收藏的商品，JOIN products 帶出 name/price/image_url/stock。"""
        raise NotImplementedError

    @abstractmethod
    def add_item(self, user_id: int, product_id: int) -> None:
        """把商品加進收藏清單；已經收藏過就當作沒事發生（冪等，不重複新增、也不報錯）。"""
        raise NotImplementedError

    @abstractmethod
    def remove_item(self, user_id: int, product_id: int) -> bool:
        """把商品從收藏清單移除；商品原本就不在清單內回傳 False。"""
        raise NotImplementedError
```

> 注意：方法簽名（參數、回傳型別）先想清楚再動手，因為等一下兩個實作（SQLite、Supabase）都要照著同一份簽名寫，之後如果要改簽名，兩邊都要一起改。

### 3.2 兩個實作各自實作

在 `sqlite_repo.py` 裡新增（做法比照 `CartRepository` 的 `_connect`/`_row_to_dict` 慣例）：

```python
class SQLiteWishlistRepository(WishlistRepository):
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def list_items(self, user_id: int) -> list[dict]:
        conn = _connect(self.db_path)
        try:
            rows = conn.execute(
                """
                SELECT p.id AS product_id, p.name, p.price, p.image_url, p.stock
                FROM wishlist_items w
                JOIN products p ON p.id = w.product_id
                WHERE w.user_id = ?
                ORDER BY w.created_at DESC
                """,
                (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def add_item(self, user_id: int, product_id: int) -> None:
        conn = _connect(self.db_path)
        try:
            # INSERT OR IGNORE + UNIQUE(user_id, product_id) 讓「重複加入」自然變成沒事發生，
            # 不需要自己先 SELECT 判斷存不存在再決定要不要 INSERT。
            conn.execute(
                "INSERT OR IGNORE INTO wishlist_items (user_id, product_id) VALUES (?, ?)",
                (user_id, product_id),
            )
            conn.commit()
        finally:
            conn.close()

    def remove_item(self, user_id: int, product_id: int) -> bool:
        conn = _connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM wishlist_items WHERE user_id = ? AND product_id = ?",
                (user_id, product_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
```

在 `supabase_repo.py` 裡比照既有 `SupabaseCartRepository` 的寫法（用 `client.table("wishlist_items")`），實作同樣三個方法，回傳格式（dict 的 key）要跟 SQLite 版完全一致，這樣 router 才能不管現在是哪個後端，用同一套程式碼處理。

### 3.3 factory.py 只需要「登記」，不需要改判斷邏輯

`factory.py` 原本依 `DB_BACKEND` 分成 `if settings.db_backend == "supabase": ... 否則 ...` 兩個分支——這個判斷邏輯本身完全不用改，只是在 `Repos` dataclass 多加一個欄位、兩個分支各多一行實例化：

```python
@dataclass
class Repos:
    users: UserRepository
    products: ProductRepository
    carts: CartRepository
    orders: OrderRepository
    wishlists: WishlistRepository   # 新增這一行
```

```python
    if settings.db_backend == "supabase":
        from app.repositories.supabase_repo import (
            SupabaseCartRepository,
            SupabaseOrderRepository,
            SupabaseProductRepository,
            SupabaseUserRepository,
            SupabaseWishlistRepository,   # 新增 import
        )
        return Repos(
            users=SupabaseUserRepository(),
            products=SupabaseProductRepository(),
            carts=SupabaseCartRepository(),
            orders=SupabaseOrderRepository(),
            wishlists=SupabaseWishlistRepository(),   # 新增這一行
        )

    from app.repositories.sqlite_repo import (
        SQLiteCartRepository,
        SQLiteOrderRepository,
        SQLiteProductRepository,
        SQLiteUserRepository,
        SQLiteWishlistRepository,   # 新增 import
    )
    return Repos(
        users=SQLiteUserRepository(db_path),
        products=SQLiteProductRepository(db_path),
        carts=SQLiteCartRepository(db_path),
        orders=SQLiteOrderRepository(db_path),
        wishlists=SQLiteWishlistRepository(db_path),   # 新增這一行
    )
```

`deps.py` 完全不用改——`get_repos()` 回傳的還是同一個 `Repos` 物件，router 只是多了一個 `repos.wishlists` 可以用。這就是抽象層帶來的好處：新增一整組資料存取能力，改動範圍精準侷限在「定義介面 + 兩份實作 + 登記進 factory」，routers 與 deps 的既有程式碼一行都不用動。

## 4. 如何新增一支 API——接續上面的 wishlist 例子

有了 Repository，接下來把它變成真正的 API 端點：

### 4.1 `schemas.py` 加 request/response 的形狀

```python
class WishlistItemOut(BaseModel):
    product_id: int
    name: str
    price: int
    image_url: str
    stock: int


class WishlistOut(BaseModel):
    items: list[WishlistItemOut]


class WishlistAddIn(BaseModel):
    """POST /api/wishlist/items 的 request body。"""
    product_id: int
```

### 4.2 新增 `app/routers/wishlist.py`

做法完全比照 `app/routers/cart.py` 的既有模式（需要登入的端點一律掛 `get_current_user` 依賴）：

```python
"""
收藏清單路由——/api/wishlist*：全部端點都需要登入。
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import Repos, get_current_user, get_repos
from app.schemas import WishlistAddIn, WishlistItemOut, WishlistOut

router = APIRouter(prefix="/api/wishlist", tags=["wishlist"])


def _build_wishlist_out(raw_items: list[dict]) -> WishlistOut:
    return WishlistOut(items=[WishlistItemOut(**item) for item in raw_items])


@router.get("", response_model=WishlistOut)
def get_wishlist(
    current_user: dict = Depends(get_current_user),
    repos: Repos = Depends(get_repos),
) -> WishlistOut:
    return _build_wishlist_out(repos.wishlists.list_items(current_user["id"]))


@router.post("/items", response_model=WishlistOut, status_code=status.HTTP_201_CREATED)
def add_to_wishlist(
    payload: WishlistAddIn,
    current_user: dict = Depends(get_current_user),
    repos: Repos = Depends(get_repos),
) -> WishlistOut:
    product = repos.products.get_by_id(payload.product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到這個商品")
    repos.wishlists.add_item(current_user["id"], payload.product_id)
    return _build_wishlist_out(repos.wishlists.list_items(current_user["id"]))


@router.delete("/items/{product_id}", response_model=WishlistOut)
def remove_from_wishlist(
    product_id: int,
    current_user: dict = Depends(get_current_user),
    repos: Repos = Depends(get_repos),
) -> WishlistOut:
    removed = repos.wishlists.remove_item(current_user["id"], product_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="收藏清單裡沒有這個商品")
    return _build_wishlist_out(repos.wishlists.list_items(current_user["id"]))
```

### 4.3 在 `main.py` 註冊路由

```python
from app.routers import auth, cart, orders, payments, products, wishlist  # 加上 wishlist

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.include_router(wishlist.router)   # 新增這一行
```

漏掉這一步的症狀：程式碼看起來寫完了、`/docs` 卻完全看不到新端點，呼叫會得到 404——這是初學者最容易忘記的一步，養成習慣「寫完 router 就去 `main.py` 確認有沒有 include」。

### 4.4 補測試：新增 `tests/test_wishlist.py`

直接沿用 `conftest.py` 現成的 `client`／`auth_headers` fixture（見第 6 節），不用自己重新建立測試資料庫：

```python
def test_add_and_list_wishlist(client, auth_headers):
    resp = client.post(
        "/api/wishlist/items",
        json={"product_id": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["items"][0]["product_id"] == 1


def test_add_wishlist_product_not_found(client, auth_headers):
    resp = client.post(
        "/api/wishlist/items",
        json={"product_id": 9999},
        headers=auth_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "找不到這個商品"


def test_wishlist_requires_login(client):
    resp = client.get("/api/wishlist")
    assert resp.status_code == 401
```

跑 `pytest tests/test_wishlist.py -v` 確認新測試先過，再跑一次全套 `pytest tests/ -q` 確認沒有把既有測試弄壞。

## 5. 如何新增一張資料表——接續 wishlist 例子的 `wishlist_items` 表

新增資料表一定要「兩份 schema 都改、欄位名稱保持一致」，這是本專案最容易漏掉一邊的地方。

### 5.1 `app/db/sqlite_schema.sql` 加一段

```sql
CREATE TABLE IF NOT EXISTS wishlist_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, product_id)   -- 同一使用者對同一商品只會有一列，「加入」天然冪等
);
CREATE INDEX IF NOT EXISTS idx_wishlist_items_user_id ON wishlist_items(user_id);
```

### 5.2 `app/db/supabase_schema.sql` 加對應的 PostgreSQL 版本

```sql
CREATE TABLE IF NOT EXISTS wishlist_items (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    product_id BIGINT NOT NULL REFERENCES products(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, product_id)
);
CREATE INDEX IF NOT EXISTS idx_wishlist_items_user_id ON wishlist_items(user_id);
```

### 5.3 Repository 實作

就是第 3 節已經寫好的 `SQLiteWishlistRepository` / `SupabaseWishlistRepository`。

### 5.4 `init_db.py`——不用改程式碼，但要注意一個限制

`scripts/init_db.py` 是把整份 `sqlite_schema.sql` 讀進來、用 `executescript()` 整份執行，`CREATE TABLE IF NOT EXISTS` 這個寫法本身就代表「已經存在的表不會被動到」，所以理論上加了新的 `CREATE TABLE` 語句、重跑 `init_db.py` 應該就能生效——**但**要注意 `init_db.py` 有一個更早的防呆判斷：如果資料庫檔案已經存在，`init_sqlite()` 會直接印出提示然後 `return`，根本不會走到執行 SQL 那一段（見腳本內註解，這是為了避免誤刪學員自己的資料）。

> 注意：這代表在一個「已經初始化過」的 `meowshop.db` 上新增資料表，有兩種選擇：
> 1. 加 `--reset` 重新建立（`python scripts/init_db.py --reset`）——最簡單，但會清空這顆資料庫裡所有既有資料（帳號、訂單都會不見），只適合還沒有正式資料、或你能接受重新來過的情境。
> 2. 手動對現有 `.db` 檔案補上這張表，例如用 `sqlite3 backend/data/meowshop.db` 進到互動模式，貼上第 5.1 節那段 `CREATE TABLE` 語句執行——這樣可以保留既有資料。
>
> 本專案沒有像 Alembic 那樣的資料庫遷移（migration）工具，這是刻意的教學簡化（詳見第 8 節），正式專案如果 schema 會持續變動，建議導入 migration 工具管理版本化的 schema 變更。

## 6. 測試怎麼寫——`conftest.py` 機制說明

`tests/conftest.py` 提供了三個關鍵 fixture，寫新測試檔時直接拿來用，不用重新發明：

- **`db_path`**（自動被 `client` 依賴，通常不用直接使用）：用 pytest 內建的 `tmp_path`（每個測試函式各自獨立、跑完自動清掉的暫存資料夾）建一顆全新的 SQLite 資料庫，套用 `sqlite_schema.sql` 建表、匯入 10 筆種子商品，並用 `monkeypatch.setenv()` 把 `DB_BACKEND`/`SQLITE_PATH`/`SECRET_KEY` 指過去。這能生效的關鍵是 `app/config.py` 的 `get_settings()` 刻意設計成「每次呼叫都重新讀 `os.environ`」，不做快取（see `config.py` 內的說明）——如果做了快取，測試改的環境變數就不會被讀到，所有測試會共用同一顆資料庫、互相污染。
- **`client`**：回傳綁定在這顆暫存資料庫上的 `TestClient`。注意 `from app.main import app` 特意寫在 fixture 函式「內部」而不是檔案最上面，確保這行執行時，環境變數已經被 `db_path` fixture 設定好了。
- **`auth_headers`** / **`register_and_login`**：幫你註冊 + 登入一個測試帳號，回傳可以直接放進 `headers=` 的 `{"Authorization": "Bearer ..."}` dict，省去每支測試都要重寫一次註冊登入流程。

新測試檔的標準寫法（照抄既有 `test_cart.py`／`test_products.py` 的模式）：

```python
def test_something(client, auth_headers):
    resp = client.post("/api/some/endpoint", json={...}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["some_field"] == "期望值"
```

不需要登入的端點，測試函式只要拿 `client` 這個 fixture，不用拿 `auth_headers`。

## 7. 程式碼慣例

- **教學註解**：每個 Python 模組頂部放一段 docstring，說明「這個檔案在整體架構的哪一層、負責什麼、關鍵設計決策的『為什麼』」；行內註解解釋「為什麼這樣寫」而不是覆述「這行程式碼做什麼」（後者程式碼本身已經講了）。新增檔案時請延續這個慣例，尤其是牽涉到「取捨」的地方（例如效能 vs 好懂、正確性 vs 簡單）。
- **金額一律用整數**：所有跟金額有關的欄位（`price`／`total_amount`／`unit_price`／`amount`）都是「新台幣整數元」，**絕對不要改成 `float` 或 `Decimal` 以外的小數型別**。這是刻意的教學設計：浮點數做金錢運算會有精度誤差（例如 `0.1 + 0.2 != 0.3`），正式金融系統絕不會直接拿 float 存錢；本專案選擇「只賣整數元商品、不用小數」來繞開這個問題，如果你的擴充功能需要「元角分」或折扣百分比這種非整數場景，要先想清楚精度策略（例如全部換算成「分」為單位的整數），不要圖方便直接上 float。
- **錯誤回應格式統一**：一律是 FastAPI 慣例的 `{"detail": "<繁中錯誤訊息>"}`，用 `HTTPException(status_code=..., detail="...")` 拋出即可，不要自創其他錯誤欄位名稱（例如 `error`／`message`）。錯誤訊息全部用繁體中文、口語，不要出現英文技術術語或 stack trace 內容外洩給前端。
- **找不到資料回 `None`／`[]`，不要丟例外**：Repository 層的慣例是「查無資料是正常業務情境」，回傳 `None`（單筆）或空 list（多筆），由 router 層決定要不要轉成 404；只有語意上明確代表「違反資料完整性」的情況（目前只有 email 重複）才用自訂例外（`DuplicateEmailError`）。新增功能如果也有類似「明確違反完整性」的情境（例如收藏清單也可以選擇用同樣模式，但本例用 `INSERT OR IGNORE` 讓「重複收藏」直接冪等處理，不需要例外），先想清楚哪一種語意比較適合再選。

## 8. 已知簡化與可擴充方向

以下是本專案為了「教學好懂、零設定就能跑」刻意做的簡化，完整討論見 `docs/PRD.md` 第 8 節：

- **JWT token 存在瀏覽器 `localStorage`**：實作簡單，但有 XSS 風險（如果網站被注入惡意 script，token 可能被偷）；正式產品常見替代方案是用 `httpOnly` cookie 存 token，瀏覽器端 JS 完全拿不到 token 內容，但需要額外處理 CSRF 防護。
- **建單不扣庫存、付款成功才扣庫存**：好處是顧客下單後反悔不會卡住庫存；壞處是同一件商品庫存只剩 1 件、兩人同時下單成功，只有先付款的人才真的扣得到庫存，後付款的人會在付款那一步才發現庫存不足。進階做法是「建單當下就『預留』庫存，付款/取消時才真正釋放或扣除」。
- **SQLite 沒有處理更細緻的交易等級併發控制**：本專案用「條件式 UPDATE」（`decrease_stock`）避免超賣，但沒有討論更複雜的交易隔離等級（isolation level）議題；Supabase 版更進一步用「樂觀鎖」模擬條件式扣減（見 `supabase_repo.py` 內註解），仍有極小的競爭空間。
- **密碼沒有強度規則、註冊沒有 email 驗證信、沒有管理後台**：目前只檢查「至少 8 碼」；沒有寄送驗證信確認 email 真實性；商品上下架/改庫存目前只能直接改資料庫或種子檔案，沒有後台介面。
- **Mock 金流沒有簽章驗證、沒有非同步回呼（webhook）**：真實金流（PayUNI、Stripe 等）會用簽章確保「這筆付款通知真的來自金流商，不是有人偽造請求」，也會用 webhook 非同步通知付款結果（因為使用者不一定會等在頁面上）；本專案的付款是「打了 API 立刻同步回結果」，跟真實金流的非同步特性不同。

**可擴充方向**（本文件已示範收藏清單，其餘留給有興趣的學員練習）：

- 收藏清單（已示範，見第 3～5 節）
- 優惠券／折扣碼（需要新表存折扣規則，訂單建立時套用）
- 商品評論與評分（需要新表，且要考慮「只有買過的人能評論」這種業務規則放在哪一層）
- 商品清單分頁（`GET /api/products` 目前一次撈全部 10 筆，商品數量變多後要加 `limit`/`offset` 或 cursor-based 分頁）
- Refresh token／token 黑名單（目前 JWT 過期後只能重新登入，沒有更細緻的登出/黑名單機制）
- Rate limiting（目前任何端點都沒有限流，正式環境要考慮防暴力破解登入、防洗版下單）
- 管理後台（商品上下架、改庫存、看所有訂單，目前只能直接動資料庫）
- 前端 E2E 測試（例如 Playwright），本專案目前只有後端 pytest，前端頁面靠人工走查
- 真實金流串接（把 `routers/payments.py` 換成真的呼叫 PayUNI/Stripe，處理簽章與 webhook）
