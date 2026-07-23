"""
Repository 抽象介面層——本教案的核心設計模式：**Repository Pattern**。

這個檔案定義了「資料要怎麼存取」的**約定（contract）**，但完全不實作「怎麼存」。
`UserRepository` / `ProductRepository` / `CartRepository` / `OrderRepository`
都是 Python 的 ABC（Abstract Base Class，抽象基底類別）：只列出方法名稱、參數、
回傳型別，方法內部寫 `raise NotImplementedError`（或用 `@abstractmethod` 強制
子類別一定要實作），本身不能被直接 `建立實例`（instantiate）使用。

為什麼要有這一層抽象？（本教案最重要的設計決策）
-----------------------------------------------------------
路由層（routers/）與商業邏輯，只認得這裡定義的方法名稱與回傳格式（純 dict），
完全不知道資料實際存在 SQLite 檔案裡還是遠端的 Supabase／PostgreSQL。
好處：
1. **可替換**：`sqlite_repo.py`（本機開發、教學示範）與 `supabase_repo.py`
   （雲端資料庫、多人協作/正式上線）是兩個完全獨立的實作，靠 `DB_BACKEND`
   環境變數切換，routers 的程式碼一行都不用改。
2. **好測試**：測試時只要能餵進一個符合介面的假物件（或指向暫存 SQLite 的
   真實 SQLiteRepository），完全不需要真的連線到雲端資料庫，測試才能又快又穩定。
3. **好理解依賴方向**：「路由層依賴抽象，不依賴具體實作」，這是很多正式後端
   框架（Java Spring、.NET 等）常見的 Repository Pattern，提早在教學專案
   建立這個概念，之後接觸更大型系統會更容易上手。

注意（初學者常見誤解）：這裡的方法全部回傳 **plain dict / list[dict]**
（key 是資料表欄位名稱），**不是** ORM 物件（例如 SQLAlchemy 的 Model instance）。
這是刻意的選擇：dict 可以直接丟進 Pydantic model 轉成 response，跨兩種資料庫
實作也不用共用同一套 ORM model 定義，降低耦合。

找不到資料時的慣例：一律回傳 `None`（單筆）或 `[]`（多筆），**不要**丟例外，
「找不到」是正常業務情境，不是例外狀況（唯一的例外是 `DuplicateEmailError`，
因為「email 重複」是明確違反資料完整性的錯誤情境，值得用例外表達）。
"""

from abc import ABC, abstractmethod


class DuplicateEmailError(Exception):
    """建立使用者時，email 已經存在——由 UserRepository.create() 主動丟出。

    為什麼用自訂例外而不是回傳 None 或 False：
    「email 重複」跟「一般查不到資料」的語意不同，呼叫端（routers/auth.py）
    需要明確分辨「這是重複註冊」才能回傳 409 加上正確的錯誤訊息；
    用專屬例外類別，呼叫端只要一個 `except DuplicateEmailError` 就能精準攔截，
    不會不小心吃掉其他非預期的錯誤。
    """


class UserRepository(ABC):
    """使用者資料存取介面。"""

    @abstractmethod
    def create(self, email: str, password_hash: str, name: str) -> dict:
        """新增一筆使用者。email 重複時必須 raise DuplicateEmailError。"""
        raise NotImplementedError

    @abstractmethod
    def get_by_email(self, email: str) -> dict | None:
        """依 email 查使用者，查無資料回傳 None。"""
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, user_id: int) -> dict | None:
        """依 id 查使用者，查無資料回傳 None。"""
        raise NotImplementedError


class ProductRepository(ABC):
    """商品資料存取介面。"""

    @abstractmethod
    def list(self, category: str | None = None, search: str | None = None) -> list[dict]:
        """列出商品，只回傳 is_active 的商品；category/search 為可選篩選條件。"""
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, product_id: int) -> dict | None:
        """依 id 查單一商品，只回傳 is_active 的商品；查無/已下架回傳 None。"""
        raise NotImplementedError

    @abstractmethod
    def decrease_stock(self, product_id: int, quantity: int) -> bool:
        """扣減庫存，庫存足夠才會真的扣，回傳是否扣成功。

        教學點——為什麼要用「條件式 UPDATE」而不是「先 SELECT 讀庫存、判斷夠不夠、
        再 UPDATE」：如果拆成兩個步驟，兩個並發的請求可能同時讀到「庫存還夠」，
        然後都各自扣一次，導致庫存變成負數（這就是經典的 race condition／超賣問題）。
        正確做法是把「檢查」跟「扣減」合成同一句 SQL：
        `UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?`
        資料庫會保證這一整句是原子操作（atomic），只有真的滿足 `stock >= ?`
        這個條件時才會真的更新，並且回傳「有幾列被更新到」，我們就用這個數字
        （1 或 0）判斷這次扣減有沒有成功，完全不需要額外加鎖。
        """
        raise NotImplementedError


class CartRepository(ABC):
    """購物車資料存取介面。"""

    @abstractmethod
    def get_items(self, user_id: int) -> list[dict]:
        """取得某使用者購物車內容，需要 JOIN products 帶出 name/price/image_url/stock。"""
        raise NotImplementedError

    @abstractmethod
    def upsert_item(self, user_id: int, product_id: int, quantity_delta: int) -> None:
        """把商品加進購物車；如果已經在購物車內，數量用「累加」而不是覆蓋。"""
        raise NotImplementedError

    @abstractmethod
    def set_quantity(self, user_id: int, product_id: int, quantity: int) -> bool:
        """直接把某商品的數量覆蓋成指定值；商品不在購物車內回傳 False。"""
        raise NotImplementedError

    @abstractmethod
    def remove_item(self, user_id: int, product_id: int) -> bool:
        """把某商品從購物車移除；商品不在購物車內回傳 False。"""
        raise NotImplementedError

    @abstractmethod
    def clear(self, user_id: int) -> None:
        """清空整個購物車（建立訂單成功後會呼叫這個）。"""
        raise NotImplementedError


class OrderRepository(ABC):
    """訂單資料存取介面。"""

    @abstractmethod
    def create(
        self,
        user_id: int,
        total_amount: int,
        recipient_name: str,
        recipient_address: str,
        items: list[dict],
    ) -> dict:
        """建立一筆訂單，同時寫入 orders 與 order_items（品項快照），回傳完整訂單詳情。

        `items` 每個 dict 需要包含：product_id, product_name, unit_price, quantity
        ——這些是「下單當下」的快照值，之後商品改名/改價都不會影響已成立的訂單。
        """
        raise NotImplementedError

    @abstractmethod
    def list_by_user(self, user_id: int) -> list[dict]:
        """列出某使用者的所有訂單（依建立時間新到舊）。"""
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, order_id: int, user_id: int) -> dict | None:
        """依 id 查單一訂單，必須同時符合 user_id（不是自己的訂單一律當作不存在）。

        回傳內容需包含 items（品項）與 payments（付款紀錄列表）。
        """
        raise NotImplementedError

    @abstractmethod
    def update_status(self, order_id: int, status: str) -> None:
        """更新訂單狀態（pending/paid/failed/cancelled）。"""
        raise NotImplementedError

    @abstractmethod
    def add_payment(
        self,
        order_id: int,
        amount: int,
        status: str,
        transaction_id: str,
        card_last4: str,
    ) -> dict:
        """新增一筆付款紀錄，回傳該筆付款紀錄。"""
        raise NotImplementedError
