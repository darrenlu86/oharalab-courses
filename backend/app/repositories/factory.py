"""
Repository 工廠——整個 Repository Pattern 能「無痛切換資料庫」的關鍵組裝點。

負責什麼：讀取 `settings.db_backend`，決定要組出 SQLite 那組實作、還是 Supabase
那組實作，包成一個 `Repos` dataclass 回傳。routers 層只透過 `deps.get_repos()`
（內部呼叫這裡的 `get_repositories()`）拿到 `Repos`，完全不用 import
`sqlite_repo` 或 `supabase_repo`，也不需要用 if/else 判斷現在是哪個後端。

為什麼要有這一層，而不是讓 routers 直接 `if settings.db_backend == "sqlite": ...`：
如果每個路由函式都自己判斷、自己 import 兩種實作，「換資料庫」這件事就會散落在
十幾個檔案裡，任何一個地方漏改就會出 bug。集中在這一個檔案，換資料庫只需要改
這裡一個地方（其實連改都不用，只要改 `.env` 的 `DB_BACKEND` 這一行環境變數）。

為什麼用 `dataclass` 而不是 4 個獨立變數：`Repos` 把「一組完整可用的資料存取層」
當成一個值傳遞，routers 用 `Depends(get_repos)` 拿到的永遠是「這次 request
該用哪一套資料庫」的完整組合，不會有「商品用了 SQLite、購物車卻用了 Supabase」
這種拼裝到一半的狀態。
"""

from dataclasses import dataclass

from app.config import get_settings
from app.repositories.base import CartRepository, OrderRepository, ProductRepository, UserRepository


@dataclass
class Repos:
    users: UserRepository
    products: ProductRepository
    carts: CartRepository
    orders: OrderRepository


def get_repositories() -> Repos:
    """依目前的 DB_BACKEND 設定，組出對應的一組 Repository 實作。"""
    settings = get_settings()

    if settings.db_backend == "supabase":
        # 延後 import：只有真的要用 Supabase 時才載入 supabase-py 相關模組，
        # 避免只想跑 SQLite（教學預設情境）的人，也被迫需要設定 SUPABASE_URL/KEY。
        from app.repositories.supabase_repo import (
            SupabaseCartRepository,
            SupabaseOrderRepository,
            SupabaseProductRepository,
            SupabaseUserRepository,
        )

        return Repos(
            users=SupabaseUserRepository(),
            products=SupabaseProductRepository(),
            carts=SupabaseCartRepository(),
            orders=SupabaseOrderRepository(),
        )

    # 預設／其餘情況一律走 SQLite——這是教學專案「零設定就能跑」的預設路徑。
    from app.repositories.sqlite_repo import (
        SQLiteCartRepository,
        SQLiteOrderRepository,
        SQLiteProductRepository,
        SQLiteUserRepository,
    )

    db_path = settings.sqlite_path
    return Repos(
        users=SQLiteUserRepository(db_path),
        products=SQLiteProductRepository(db_path),
        carts=SQLiteCartRepository(db_path),
        orders=SQLiteOrderRepository(db_path),
    )
