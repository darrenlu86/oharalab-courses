"""
商品列表的 in-memory TTL 快取——本階段新增，stage5 完全沒有這個檔案。

為什麼要快取商品列表：`GET /api/products` 是全站打最頻繁的端點（首頁、商品頁、
分類頁都會呼叫），但商品資料變動很少（只有 admin 新增/編輯/上下架商品時才會變）。
每次都真的查一次 SQLite 對單機教學規模來說不算慢，但這是「效能調校」單元最基本、
最常見的一課：**讀多寫少的資料，值得用記憶體快取擋在資料庫前面**，換取更低的延遲
與更小的資料庫負載。

為什麼是「TTL 快取」而不是「永久快取＋手動失效」：兩者都要處理 cache invalidation
（見下方 `invalidate()`），但 TTL 多一層保險——就算某個呼叫端忘記呼叫
`invalidate()`（例如未來新增了另一支會改到 products 表的端點，卻忘記通知快取），
最多也只會讓使用者看到過期 30 秒的資料，不會永遠卡住。這是「用資料新鮮度換系統
簡單度」的典型取捨，30 秒的教學設定值刻意選得夠短（使用者感覺不出明顯延遲）又
夠長（足以在課堂 demo 時看到「有快取」跟「沒快取」的行為差異）。

**為什麼這是教學簡化，正式產品要注意什麼**：這個快取活在單一 Python process 的
記憶體裡。stage6 spec 明確要求「uvicorn workers 概念」只寫教學文件、不真的啟用
多 worker（見 docs/ARCHITECTURE.md「uvicorn workers」一節）——因為如果真的開了
多個 worker process，每個 worker 會有自己獨立的一份快取，某個 worker 收到
「商品已更新」的失效通知，其他 worker 完全不知道，會出現「後台明明改好了，前台
有些請求還是看到舊資料」的不一致，正式產品要解決這個問題通常會改用 Redis 這種
「所有 worker 共享同一份快取」的外部儲存，這正是本階段刻意不做多 worker 的原因。
"""

import time
from typing import Callable


class TTLCache:
    """極簡的記憶體 TTL 快取：key -> (value, 到期時間)。

    `clock` 參數預設是 `time.monotonic`（不受系統時間被使用者調整影響，計時更可靠），
    測試時可以注入一個假的 clock 函式，不用真的等待 30 秒就能驗證「過期後應該
    重新查資料庫」的行為，見 tests/test_cache.py。
    """

    def __init__(self, ttl_seconds: float = 30.0, clock: Callable[[], float] = time.monotonic):
        self.ttl_seconds = ttl_seconds
        self._clock = clock
        self._store: dict[tuple, tuple[object, float]] = {}

    def get(self, key: tuple):
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if self._clock() >= expires_at:
            # 過期就直接從字典裡刪掉，而不是留著等下次覆寫——避免字典無限長大
            # （雖然本專案的 key 組合本來就有限，但這是正確的教學習慣）。
            del self._store[key]
            return None
        return value

    def set(self, key: tuple, value: object) -> None:
        self._store[key] = (value, self._clock() + self.ttl_seconds)

    def invalidate_all(self) -> None:
        """商品被新增/編輯/上下架時呼叫——這是「cache invalidation 很難」這句老話
        在本專案的具體示範：我們選擇最簡單粗暴但絕對正確的策略「整包快取全部清空」，
        而不是「只清掉被改到那個商品相關的 key」。理由：本專案的快取 key 是
        `(category, search)` 組合（見 app/routers/products.py），一個商品被編輯後，
        可能同時影響好幾種篩選組合的結果（例如改了分類，舊分類的列表跟新分類的
        列表都要更新），精準判斷「這次改動會影響哪些 key」比整包清空複雜得多，
        對教學規模的資料量，全部清空的成本可以忽略不計。
        """
        self._store.clear()

    def size(self) -> int:
        return len(self._store)


# 全站共用單例——products.py 讀取、admin.py 在商品異動後呼叫 invalidate_all()。
# 用模組層級變數當單例，是 Python 最簡單的作法（同一個 process 內，同一個模組
# 只會被 import 一次，`from app.cache import products_cache` 到處拿到的都是
# 同一個物件）；跟 app/config.py 的 Settings 刻意「不」做成單例是相反的考量——
# 這裡的快取狀態本來就應該全站共用，而不是每次呼叫都重新建一個空的。
products_cache = TTLCache(ttl_seconds=30.0)
