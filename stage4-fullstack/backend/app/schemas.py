"""
Schema 層——全部的 Pydantic request/response models。

跟 meowshop 的 schemas.py 同一套風格：這裡只負責「資料形狀」（型別、必填、格式），
不含商業邏輯；「這個 email 是不是已經註冊過」這種要查資料庫才知道的規則，
是在 routers 裡呼叫 app/db/database.py 之後才處理。
"""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

ProductCategory = Literal["beans", "drip", "gear", "cups", "gift"]
OrderStatus = Literal["pending"]

# SQLite 的 INTEGER 欄位是 64-bit 有號整數，Python 的 int 本身沒有這個上限——
# 外部傳進來的 id（超過這個範圍的整數字面上完全合法，例如 20 位數）如果直接
# 拿去綁定 SQL 參數，`sqlite3` 模組會丟出未被接住的 `OverflowError`，最後變成
# 一支查一個不存在商品也會出現的 500。這裡先在 schema 層擋下來，讓這種輸入
# 停在「格式不對」（422），不要讓它有機會摸到資料庫層。
SQLITE_INT64_MAX = 9223372036854775807

# 一筆訂單品項的合理數量上限——教學用途的商店，不會有人一次買一萬件咖啡豆，
# 這裡刻意選一個遠高於任何正常使用情境、但又不到 SQLite 上限的數字，純粹是
# 「擋掉離譜輸入」的防呆線，不是真的業務規則（沒有任何 spec 文件規定確切數字）。
MAX_ITEM_QUANTITY = 1000


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
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: int
    email: str
    name: str


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


class ProductListOut(BaseModel):
    items: list[ProductOut]
    total: int


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
    status: str
    total_amount: int
    recipient_name: str
    recipient_address: str
    created_at: str
    updated_at: str


class OrderListOut(BaseModel):
    items: list[OrderSummaryOut]


class OrderDetailOut(OrderSummaryOut):
    items: list[OrderItemOut]


# ---------- 其他 ----------


class HealthOut(BaseModel):
    status: str
