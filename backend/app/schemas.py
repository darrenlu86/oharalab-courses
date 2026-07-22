"""
Schema 層——全部的 Pydantic request/response models 都放這裡。

負責什麼：定義每個 API 端點「收進來的資料長什麼樣子」（request body）與
「回傳出去的資料長什麼樣子」（response model）。FastAPI 會自動用這些 class
做資料驗證（格式錯就自動回 422）與自動產生 API 文件（/docs）。

在架構中的位置：純粹的資料形狀定義，不含任何商業邏輯，routers/ 裡的函式會
import 這裡的 class 當作參數型別與回傳型別。

注意：這裡的 model 只負責「資料形狀」，例如「email 是不是合法 email 格式」
「密碼至少 8 碼」；至於「這個 email 是不是已經註冊過」這種要查資料庫才知道的規則，
不屬於 schema 驗證的範圍，是在 routers 裡呼叫 repository 之後才處理。
"""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

ProductCategory = Literal["food", "snack", "toy", "litter", "supplies"]
OrderStatus = Literal["pending", "paid", "failed", "cancelled"]


# ---------- 認證 auth ----------


class UserCreate(BaseModel):
    """POST /api/auth/register 的 request body。"""

    email: EmailStr
    password: str = Field(min_length=8, description="至少 8 碼")
    name: str = Field(min_length=1)

    @field_validator("password")
    @classmethod
    def validate_password_length(cls, value: str) -> str:
        # 教學點——為什麼要檢查「位元組數」而不是「字數」：bcrypt 演算法本身
        # 有 72 bytes 的密碼長度上限（這是 bcrypt 演算法規格的限制，不是這個
        # 專案自己加的規則）。英文字母 1 個字 = 1 byte，但中文字在 UTF-8 編碼
        # 下 1 個字通常是 3 bytes，所以不能用 len(密碼字串) 來判斷，一定要先
        # `.encode("utf-8")` 再看 bytes 長度，否則中文使用者會在字數看起來
        # 明明沒超過限制時就被拒絕（或反過來，英文長密碼字數沒超但 bytes 超了）。
        # 在這裡（schema 驗證層）就擋下來，好處是失敗會很自然地變成 FastAPI
        # 標準的 422 回應，跟其他欄位驗證錯誤的形狀一致，不需要 routers 層
        # 額外寫 try/except 去接 security.py 丟出來的例外。
        if len(value.encode("utf-8")) > 72:
            raise ValueError("密碼太長：最長 72 個位元組（bcrypt 演算法的限制）")
        return value


class UserLogin(BaseModel):
    """POST /api/auth/login 的 request body。"""

    email: EmailStr
    password: str


class UserPublic(BaseModel):
    """對外公開的使用者資訊（絕對不含 password_hash）。"""

    id: int
    email: str
    name: str


class UserOut(UserPublic):
    """/api/auth/register 與 /api/auth/me 的 response，多帶 created_at。"""

    created_at: str


class TokenOut(BaseModel):
    """/api/auth/login 成功後的 response。"""

    access_token: str
    token_type: str = "bearer"
    user: UserPublic


# ---------- 商品 products ----------


class ProductOut(BaseModel):
    """商品清單／詳情共用的 response 形狀。"""

    id: int
    name: str
    description: str
    price: int  # 教學點：金額一律用整數（新台幣元），不要用 float 存錢
    stock: int
    category: str
    image_url: str
    is_active: bool


class ProductListOut(BaseModel):
    items: list[ProductOut]
    total: int


# ---------- 購物車 cart ----------


class CartItemIn(BaseModel):
    """POST /api/cart/items 的 request body。"""

    product_id: int
    quantity: int = Field(ge=1)


class CartQuantityIn(BaseModel):
    """PATCH /api/cart/items/{product_id} 的 request body。"""

    quantity: int = Field(ge=1)


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
    """POST /api/orders 的 request body。"""

    recipient_name: str = Field(min_length=1)
    recipient_address: str = Field(min_length=1)


class OrderItemOut(BaseModel):
    """訂單內的單一品項——注意這是「下單當下的快照」，欄位刻意跟 products 分開存。"""

    product_id: int
    product_name: str
    unit_price: int
    quantity: int


class PaymentRecordOut(BaseModel):
    """附掛在訂單詳情裡的付款紀錄（一筆訂單可能有多次付款嘗試，例如先失敗後重付）。"""

    id: int
    amount: int
    method: str
    status: str
    transaction_id: str
    card_last4: str
    created_at: str


class OrderSummaryOut(BaseModel):
    """GET /api/orders 清單裡的單筆摘要，不含品項明細。"""

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
    """GET /api/orders/{id} 與 POST /api/orders 的完整訂單詳情。"""

    items: list[OrderItemOut]
    payments: list[PaymentRecordOut]


# ---------- 付款 payments ----------


class PaymentMockIn(BaseModel):
    """POST /api/payments/mock 的 request body。"""

    order_id: int
    card_number: str
    card_holder: str = Field(min_length=1)

    @field_validator("card_number")
    @classmethod
    def validate_card_number(cls, value: str) -> str:
        # 注意：規格允許卡號「可含空格」（例如 4242 4242 4242 4242），
        # 所以驗證前要先把空格去掉，只留數字本體再檢查長度。
        digits_only = value.replace(" ", "")
        if not digits_only.isdigit() or len(digits_only) != 16:
            raise ValueError("卡號必須是 16 碼數字（可包含空格分隔）")
        return digits_only


class PaymentOut(BaseModel):
    transaction_id: str
    status: str
    amount: int
    card_last4: str


class OrderBriefOut(BaseModel):
    """付款 response 裡精簡的訂單資訊，只需要 id 跟最新 status。"""

    id: int
    status: str


class PaymentMockOut(BaseModel):
    payment: PaymentOut
    order: OrderBriefOut


# ---------- 其他 ----------


class HealthOut(BaseModel):
    status: str
    db_backend: str
