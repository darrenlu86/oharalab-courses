"""
Schema 層——全部的 Pydantic request/response models。

跟 meowshop 的 schemas.py 同一套風格：這裡只負責「資料形狀」（型別、必填、格式），
不含商業邏輯；「這個 email 是不是已經註冊過」這種要查資料庫才知道的規則，
是在 routers 裡呼叫 app/db/database.py 之後才處理。

跟 stage4 的差異（逐項見 docs/API.md 開頭「與上一階段的差異」）：
1. `UserPublic` 多了 `role` 欄位——前端（尤其是 admin app）需要知道「登入的是不是
   管理員」才能決定要不要放行、要不要顯示後台選單。
2. `OrderStatus` 從只有 `'pending'` 一種，擴充成完整的六種狀態。
3. 新增 `ProductOut.is_active`、`ProductAdminCreateIn` / `ProductAdminUpdateIn`。
4. 新增付款相關 schema（`PaymentIn` / `PaymentOut`）、訂單狀態變更（`OrderStatusUpdateIn`）、
   後台聚合（`AdminSummaryOut`）、後台會員清單（`AdminUserOut`）。
"""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

ProductCategory = Literal["beans", "drip", "gear", "cups", "gift"]
OrderStatus = Literal["pending", "paid", "failed", "shipped", "completed", "cancelled"]
UserRole = Literal["customer", "admin"]

# SQLite 的 INTEGER 欄位是 64-bit 有號整數，Python 的 int 本身沒有這個上限——
# 外部傳進來的 id（超過這個範圍的整數字面上完全合法，例如 20 位數）如果直接
# 拿去綁定 SQL 參數，`sqlite3` 模組會丟出未被接住的 `OverflowError`，最後變成
# 一支查一個不存在資源也會出現的 500。這裡先在 schema 層擋下來，讓這種輸入
# 停在「格式不對」（422），不要讓它有機會摸到資料庫層。
SQLITE_INT64_MAX = 9223372036854775807

# 一筆訂單品項的合理數量上限——教學用途的商店，不會有人一次買一萬件咖啡豆，
# 這裡刻意選一個遠高於任何正常使用情境、但又不到 SQLite 上限的數字，純粹是
# 「擋掉離譜輸入」的防呆線，不是真的業務規則（沒有任何 spec 文件規定確切數字）。
MAX_ITEM_QUANTITY = 1000

# 後台商品欄位的合理上限——種子資料價格落在 NT$300~1580、庫存落在 0~50
# （見 app/db/seed_products.json），這裡抓一個遠高於任何真實商品的數字當防呆線，
# 教學重點是「擋掉離譜輸入」，不是模擬真實店家的商品分級或訂價策略。
MAX_PRODUCT_PRICE = 10_000_000
MAX_PRODUCT_STOCK = 1_000_000


# ---------- 認證 auth ----------


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="至少 8 碼")
    name: str = Field(min_length=1)

    @field_validator("password")
    @classmethod
    def validate_password_length(cls, value: str) -> str:
        # bcrypt 演算法本身有 72 bytes 的密碼長度上限，要看 UTF-8 位元組數而不是
        # 字數（中文一個字通常是 3 bytes）。理由與 meowshop 的同名驗證器一致。
        if len(value.encode("utf-8")) > 72:
            raise ValueError("密碼太長：最長 72 個位元組（bcrypt 演算法的限制）")
        return value


class UserLogin(BaseModel):
    # 刻意用 `str`（不是 `EmailStr`）：登入端點的 email 格式驗證意義不大——這裡
    # 只是拿字串去資料庫比對，格式不對本來就會查無此人、回一樣的「email 或密碼
    # 錯誤」。改用 EmailStr 反而會誤傷合法帳號：`app.security` 套件用的
    # email-validator 2.x 預設會拒絕 IANA 保留給文件/測試用途的特殊網域（.test /
    # .invalid / .localhost / .arpa / .onion，見 RFC 2606），而 master spec 規定
    # 的測試帳號 email 剛好是 `@brewgo.test`——如果這裡繼續用 EmailStr，
    # 連 seed 出來的官方測試帳號自己都登入不了，這是實測抓到的行為（見
    # docs/API.md「已知限制」一節）。`UserCreate.email`（註冊用）維持 EmailStr，
    # 新註冊帳號的格式驗證還是有意義的。
    email: str = Field(min_length=3)
    password: str


class UserPublic(BaseModel):
    id: int
    email: str
    name: str
    role: UserRole


class UserOut(UserPublic):
    created_at: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


# ---------- 商品 products ----------


class ProductOut(BaseModel):
    id: int
    name: str
    description: str
    price: int  # 金額一律用整數（新台幣元），不要用 float 存錢
    stock: int
    category: str
    image_url: str
    is_active: bool


class ProductListOut(BaseModel):
    items: list[ProductOut]
    total: int


class ProductAdminCreateIn(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    price: int = Field(gt=0, le=MAX_PRODUCT_PRICE)
    stock: int = Field(ge=0, le=MAX_PRODUCT_STOCK)
    category: ProductCategory
    image_url: str = Field(min_length=1)


class ProductAdminUpdateIn(BaseModel):
    """後台商品編輯——全部欄位都可省略（None＝這欄不改）。"""

    name: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, min_length=1)
    price: int | None = Field(default=None, gt=0, le=MAX_PRODUCT_PRICE)
    stock: int | None = Field(default=None, ge=0, le=MAX_PRODUCT_STOCK)
    category: ProductCategory | None = None
    image_url: str | None = Field(default=None, min_length=1)
    is_active: bool | None = None


# ---------- 購物車 cart ----------


class CartItemIn(BaseModel):
    product_id: int = Field(ge=1, le=SQLITE_INT64_MAX)
    quantity: int = Field(ge=1, le=MAX_ITEM_QUANTITY)


class CartQuantityIn(BaseModel):
    quantity: int = Field(ge=1, le=MAX_ITEM_QUANTITY)


class CartItemOut(BaseModel):
    product_id: int
    name: str
    price: int
    image_url: str
    quantity: int
    stock: int
    # 商品目前是否仍在架上——下架不會把品項從購物車移除（見
    # app/db/database.py `get_cart_items()` 的說明），這裡把最新狀態一起帶給
    # 前端，讓「購物車頁顯示『已下架』徽章、停用該品項數量調整、結帳按鈕先
    # 擋一次」這件事有資料可以依據，而不是要使用者建單被 409 之後才知道。
    is_active: bool
    subtotal: int


class CartOut(BaseModel):
    items: list[CartItemOut]
    total_amount: int
    total_quantity: int


# ---------- 訂單 orders ----------


class OrderCreateIn(BaseModel):
    recipient_name: str = Field(min_length=1)
    recipient_address: str = Field(min_length=1)


class OrderItemOut(BaseModel):
    """訂單內的單一品項——下單當下的快照，欄位刻意跟 products 表分開存。"""

    product_id: int
    product_name: str
    unit_price: int
    quantity: int


class OrderSummaryOut(BaseModel):
    id: int
    status: OrderStatus
    total_amount: int
    recipient_name: str
    recipient_address: str
    created_at: str
    updated_at: str


class OrderListOut(BaseModel):
    items: list[OrderSummaryOut]


class OrderDetailOut(OrderSummaryOut):
    items: list[OrderItemOut]


class AdminOrderOut(OrderDetailOut):
    """後台訂單詳情——比顧客看到的多一個 user_id，方便對照是哪個會員下的單。"""

    user_id: int


class AdminOrderListOut(BaseModel):
    items: list[AdminOrderOut]


class OrderStatusUpdateIn(BaseModel):
    status: OrderStatus


# ---------- 付款 payments ----------


class PaymentIn(BaseModel):
    order_id: int = Field(ge=1, le=SQLITE_INT64_MAX)
    card_number: str = Field(min_length=13, max_length=19, description="測試卡號，僅接受數字與空白")
    card_holder: str = Field(min_length=1)

    @field_validator("card_number")
    @classmethod
    def validate_card_number(cls, value: str) -> str:
        digits = value.replace(" ", "")
        if not digits.isdigit():
            raise ValueError("卡號只能包含數字（可以有空白分隔）")
        return digits


class PaymentOut(BaseModel):
    id: int
    order_id: int
    amount: int
    card_last4: str
    status: Literal["success", "failed"]
    created_at: str


class PaymentResultOut(BaseModel):
    payment: PaymentOut
    order: OrderDetailOut


# ---------- 後台 admin ----------


class AdminSummaryOut(BaseModel):
    total_revenue: int
    total_orders: int
    pending_shipment_orders: int
    low_stock_products: list[ProductOut]
    member_count: int


class AdminUserOut(BaseModel):
    id: int
    email: str
    name: str
    role: UserRole
    created_at: str


class AdminUserListOut(BaseModel):
    items: list[AdminUserOut]


# ---------- 其他 ----------


class HealthOut(BaseModel):
    status: str
