"""
Supabase 版的 Repository 實作——`DB_BACKEND=supabase` 時使用，資料實際存在雲端的
Supabase（背後就是一台 PostgreSQL）。

在架構中的位置：跟 `sqlite_repo.py` 一樣實作 `base.py` 定義的四個抽象介面，
`factory.py` 會依 `DB_BACKEND` 決定要組裝哪一組。routers 層完全不需要知道
現在是哪一個實作在跑。

寫這個檔案之前，已經用 Context7 查證 `supabase-py`（官方 Python client）的實際 API
（table().insert/select/update/delete/eq/ilike/order 的用法、`APIError` 的屬性），
不是憑印象亂寫。以下是幾個查證後才確定的關鍵行為：

1. `insert()` / `update()` / `delete()` 執行後，`response.data` 預設就是「被影響的那些
   列」組成的 list[dict]（PostgREST 的 `Prefer: return=representation`），所以插入後
   要拿回新資料的 id，不需要再多查一次，直接讀 `response.data[0]` 即可。
2. 查無資料時 `response.data` 會是空 list `[]`，不是 `None`，所以判斷「找不到」要用
   `if not response.data`，不能直接 `is None`。
3. UNIQUE 約束衝突（例如 email 重複）時，`insert()` 不會回傳空結果，而是直接丟出
   `postgrest.exceptions.APIError`，錯誤物件的 `.code` 屬性就是 PostgreSQL 的
   error code；違反 UNIQUE 約束固定是 `"23505"`，所以用 `exc.code == "23505"`
   判斷「這是重複 email」，跟其他種類的錯誤（例如網路斷線）分開處理。
4. 一對多的關聯資料可以直接用巢狀 `select("*, order_items(*), payments(*)")` 一次
   撈回來（PostgREST 會依外鍵關聯自動 JOIN），不需要自己手動拆成兩三次查詢再拼。

已知簡化（Supabase 路徑不在本專案自動化測試範圍內，正確性由 code review 把關）：
- PostgREST 是無狀態的 REST API，`supabase-py` 沒有提供「跨資料表的 client 端交易」
  （例如同時新增 orders + order_items、其中一句失敗要整批回滾）；正式環境要做到
  真正的 all-or-nothing，需要在 Postgres 裡寫 RPC function 再用 `.rpc()` 呼叫。
  這裡教學用途先用「依序呼叫兩次 insert」示範，簡單但不是嚴格原子的。
- `decrease_stock()` 沒辦法像 SQLite 版一樣，一句 SQL 就做到「條件式扣減」
  （PostgREST 的 update 只能送固定數值，沒辦法送 `stock = stock - 1` 這種運算式），
  這裡改用「先讀出目前庫存 → 檢查夠不夠 → 用『同時比對舊庫存值』的條件式 UPDATE
  當作樂觀鎖（optimistic concurrency control）」。如果兩個請求在讀取之後、寫入之前
  的極短時間內同時搶購最後一件商品，這個做法仍然可能有極小的競爭空間；
  SQLite 版的條件式 UPDATE 才是本教案示範「完全原子」的版本。
"""

from datetime import datetime, timezone

from postgrest.exceptions import APIError
from supabase import Client, create_client

from app.config import get_settings
from app.repositories.base import (
    CartRepository,
    DuplicateEmailError,
    OrderRepository,
    ProductRepository,
    UserRepository,
)

# 模組級單例：整個 process 共用同一個 Supabase client，不用每次呼叫都重新建立連線。
# 用 lazy initialization（第一次用到才建立）而不是在 import 當下就建立，
# 是為了讓「DB_BACKEND=sqlite 的人」完全不需要設定 SUPABASE_URL/SUPABASE_KEY
# 也能正常 import 這個檔案（例如跑測試時，這個模組還是會被 factory.py import 到）。
_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        settings = get_settings()
        _client = create_client(settings.supabase_url, settings.supabase_key)
    return _client


class SupabaseUserRepository(UserRepository):
    def create(self, email: str, password_hash: str, name: str) -> dict:
        client = _get_client()
        try:
            response = (
                client.table("users")
                .insert({"email": email, "password_hash": password_hash, "name": name})
                .execute()
            )
        except APIError as exc:
            # 23505 = PostgreSQL 的 unique_violation error code，代表違反 UNIQUE 約束。
            if exc.code == "23505":
                raise DuplicateEmailError(email) from exc
            raise
        return response.data[0]

    def get_by_email(self, email: str) -> dict | None:
        client = _get_client()
        response = client.table("users").select("*").eq("email", email).execute()
        return response.data[0] if response.data else None

    def get_by_id(self, user_id: int) -> dict | None:
        client = _get_client()
        response = client.table("users").select("*").eq("id", user_id).execute()
        return response.data[0] if response.data else None


class SupabaseProductRepository(ProductRepository):
    def list(self, category: str | None = None, search: str | None = None) -> list[dict]:
        client = _get_client()
        query = client.table("products").select("*").eq("is_active", True)
        if category:
            query = query.eq("category", category)
        if search:
            # ilike = 不分大小寫的 LIKE，中文比對本來就沒有大小寫問題，
            # 但商品名稱如果混英文（例如品牌名），ilike 比較符合使用者直覺。
            query = query.ilike("name", f"%{search}%")
        response = query.order("id").execute()
        return response.data

    def get_by_id(self, product_id: int) -> dict | None:
        client = _get_client()
        response = (
            client.table("products")
            .select("*")
            .eq("id", product_id)
            .eq("is_active", True)
            .execute()
        )
        return response.data[0] if response.data else None

    def decrease_stock(self, product_id: int, quantity: int) -> bool:
        client = _get_client()
        # 第一步：讀出目前庫存。
        read_resp = client.table("products").select("stock").eq("id", product_id).execute()
        if not read_resp.data:
            return False
        current_stock = read_resp.data[0]["stock"]
        if current_stock < quantity:
            return False
        new_stock = current_stock - quantity
        # 第二步：條件式寫入——在 WHERE 條件裡「同時比對 id 與剛剛讀到的舊庫存值」，
        # 如果這段時間內庫存已經被別的請求改變，這個條件就不會成立，
        # response.data 會是空的，代表這次扣減沒有生效（需要呼叫端自行決定要不要重試）。
        update_resp = (
            client.table("products")
            .update({"stock": new_stock})
            .eq("id", product_id)
            .eq("stock", current_stock)
            .execute()
        )
        return len(update_resp.data) > 0


class SupabaseCartRepository(CartRepository):
    def get_items(self, user_id: int) -> list[dict]:
        client = _get_client()
        # 用巢狀 select 一次把 cart_items JOIN products 撈回來，
        # PostgREST 會依照 cart_items.product_id → products.id 的外鍵自動關聯。
        response = (
            client.table("cart_items")
            .select("product_id, quantity, products(name, price, image_url, stock, is_active)")
            .eq("user_id", user_id)
            .order("id")
            .execute()
        )
        # 教學點——為什麼要濾掉 is_active=False 的商品（跟 sqlite_repo.py 對稱）：
        # 商品下架後，如果不過濾，購物車會繼續顯示一件「看起來正常」的商品，
        # 但建單時 orders.py 用的是有過濾 is_active 的 get_by_id()，查不到商品，
        # 會回報「庫存不足」，其實真正原因是商品已下架，訊息文不對題容易誤導人。
        # 下架商品從購物車直接「消失」是教學簡化，真實系統通常會保留該筆
        # cart_items 並標示「已下架，請移除」，而不是默默消失。
        items = []
        for row in response.data:
            product = row.get("products") or {}
            if not product.get("is_active", False):
                continue
            items.append(
                {
                    "product_id": row["product_id"],
                    "quantity": row["quantity"],
                    "name": product.get("name"),
                    "price": product.get("price"),
                    "image_url": product.get("image_url"),
                    "stock": product.get("stock"),
                }
            )
        return items

    def upsert_item(self, user_id: int, product_id: int, quantity_delta: int) -> None:
        client = _get_client()
        # 注意：這裡刻意不用 client 內建的 upsert()，因為 upsert() 的語意是
        # 「衝突時用新值覆蓋整列」，沒辦法表達「數量用累加」；所以改成
        # 「先查現有數量 → 有就更新成『舊值 + delta』，沒有就直接新增」。
        #
        # 教學點——為什麼這樣「先查後寫」不是原子操作、以及為什麼要捕捉 23505：
        # 上面這行 select 到下面的 insert 之間有時間差（兩次獨立的 HTTP 呼叫），
        # 如果同一個使用者對同一件商品連按兩次「加入購物車」（網路稍慢、或前端
        # 因為使用者體感沒反應而重複送出，這是很常見的真實使用者行為），
        # 兩個請求的 select 都可能查到「還不存在」，於是都各自呼叫 insert()；
        # cart_items 有 UNIQUE(user_id, product_id) 約束，第二個 insert 會在
        # PostgREST 端違反唯一鍵，丟出 `APIError`（`.code == "23505"`，
        # PostgreSQL 的 unique_violation）。如果不接住，使用者會看到一個
        # 沒有處理過的 500；這裡接住之後改成「重查一次現有列、用 update 累加」
        # 重試一次，讓使用者體驗跟 SQLite 版的單句原子 UPSERT 一致（仍有極小
        # 殘留競爭視窗，但不會讓使用者看到原始 500）。
        existing = (
            client.table("cart_items")
            .select("id, quantity")
            .eq("user_id", user_id)
            .eq("product_id", product_id)
            .execute()
        )
        if existing.data:
            row = existing.data[0]
            new_quantity = row["quantity"] + quantity_delta
            client.table("cart_items").update({"quantity": new_quantity}).eq(
                "id", row["id"]
            ).execute()
            return

        try:
            client.table("cart_items").insert(
                {"user_id": user_id, "product_id": product_id, "quantity": quantity_delta}
            ).execute()
        except APIError as exc:
            if exc.code != "23505":
                raise
            # 併發的另一個請求搶先 insert 成功了：重查一次現有列，改用 update 累加。
            retry_existing = (
                client.table("cart_items")
                .select("id, quantity")
                .eq("user_id", user_id)
                .eq("product_id", product_id)
                .execute()
            )
            if not retry_existing.data:
                # 極端情況（例如同時被刪除）；理論上打不到，直接把原始例外拋出去。
                raise
            retry_row = retry_existing.data[0]
            retry_quantity = retry_row["quantity"] + quantity_delta
            client.table("cart_items").update({"quantity": retry_quantity}).eq(
                "id", retry_row["id"]
            ).execute()

    def set_quantity(self, user_id: int, product_id: int, quantity: int) -> bool:
        client = _get_client()
        response = (
            client.table("cart_items")
            .update({"quantity": quantity})
            .eq("user_id", user_id)
            .eq("product_id", product_id)
            .execute()
        )
        return len(response.data) > 0

    def remove_item(self, user_id: int, product_id: int) -> bool:
        client = _get_client()
        response = (
            client.table("cart_items")
            .delete()
            .eq("user_id", user_id)
            .eq("product_id", product_id)
            .execute()
        )
        return len(response.data) > 0

    def clear(self, user_id: int) -> None:
        client = _get_client()
        client.table("cart_items").delete().eq("user_id", user_id).execute()


class SupabaseOrderRepository(OrderRepository):
    def create(
        self,
        user_id: int,
        total_amount: int,
        recipient_name: str,
        recipient_address: str,
        items: list[dict],
    ) -> dict:
        client = _get_client()
        order_response = (
            client.table("orders")
            .insert(
                {
                    "user_id": user_id,
                    "total_amount": total_amount,
                    "status": "pending",
                    "recipient_name": recipient_name,
                    "recipient_address": recipient_address,
                }
            )
            .execute()
        )
        order_id = order_response.data[0]["id"]
        # 逐筆 insert order_items（而不是一次塞一個 list）：這是查證過、確定安全的
        # 單筆 insert 用法；訂單品項通常也就幾筆，效能差異可以忽略。
        for item in items:
            client.table("order_items").insert(
                {
                    "order_id": order_id,
                    "product_id": item["product_id"],
                    "product_name": item["product_name"],
                    "unit_price": item["unit_price"],
                    "quantity": item["quantity"],
                }
            ).execute()
        return self.get_by_id(order_id, user_id)

    def list_by_user(self, user_id: int) -> list[dict]:
        client = _get_client()
        # 注意：這裡只用 created_at 一個欄位排序，不像 SQLite 版還額外加 id 當 tie-breaker
        # ——因為 PostgreSQL 的 TIMESTAMPTZ 有微秒精度，兩筆訂單在同一微秒內建立的
        # 機率極低，不像 SQLite 的 datetime('now') 只有到「秒」的精度那麼容易撞期。
        response = (
            client.table("orders")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return response.data

    def get_by_id(self, order_id: int, user_id: int) -> dict | None:
        client = _get_client()
        # 教學點——為什麼巢狀 select 要明確加 .order(..., foreign_table=...)：
        # PostgreSQL／PostgREST 在沒有明確 ORDER BY 時不保證回傳列的順序
        # （即使實務上常常剛好接近插入順序，也不是規格保證的行為）。
        # sqlite_repo.py 的 _get_full_order() 對 order_items／payments 都下了
        # `ORDER BY id`，這裡也要用 id 升冪排序，兩邊後端對同一張訂單回傳的
        # items/payments 陣列順序才會一致，符合 SPEC 對兩種實作「回傳形狀
        # 要一致」的要求，也避免學員對照兩種後端輸出時，誤以為順序跳動是資料壞了。
        response = (
            client.table("orders")
            .select("*, order_items(*), payments(*)")
            .eq("id", order_id)
            .eq("user_id", user_id)
            .order("id", foreign_table="order_items")
            .order("id", foreign_table="payments")
            .execute()
        )
        if not response.data:
            return None
        order = dict(response.data[0])
        # PostgREST 巢狀查詢回來的關聯資料，key 名稱就是「表名」（order_items），
        # 這裡轉成跟 SQLite 版一致的 "items" key，讓 routers 層不用管兩種實作的差異。
        order["items"] = order.pop("order_items", [])
        return order

    def update_status(self, order_id: int, status: str) -> None:
        client = _get_client()
        # updated_at 沒有資料庫層級的「on update 自動更新」機制（PostgreSQL 預設只有
        # insert 時的 DEFAULT now()，update 要自己帶新值，除非額外寫 trigger），
        # 所以這裡從 Python 端明確帶上目前時間。
        now = datetime.now(timezone.utc).isoformat()
        client.table("orders").update({"status": status, "updated_at": now}).eq(
            "id", order_id
        ).execute()

    def add_payment(
        self,
        order_id: int,
        amount: int,
        status: str,
        transaction_id: str,
        card_last4: str,
    ) -> dict:
        client = _get_client()
        response = (
            client.table("payments")
            .insert(
                {
                    "order_id": order_id,
                    "amount": amount,
                    "method": "mock_card",
                    "status": status,
                    "transaction_id": transaction_id,
                    "card_last4": card_last4,
                }
            )
            .execute()
        )
        return response.data[0]
