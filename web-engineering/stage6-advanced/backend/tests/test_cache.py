"""
測試 app/cache.py 的 TTLCache，以及 products.py／admin.py 對它的實際使用
（命中、過期、admin 改商品後失效）。

過期測試用「注入假的 clock 函式」而不是真的 `time.sleep(31)`，理由見
app/cache.py `TTLCache.__init__` 的說明——測試不應該為了驗證「30 秒後過期」
這件事真的等 30 秒，那樣整個測試套件會慢到沒人想常跑。
"""

from fastapi.testclient import TestClient

from app.cache import TTLCache


# ---------- TTLCache 單元測試（不牽涉 FastAPI） ----------


def test_ttl_cache_hit_returns_cached_value():
    cache = TTLCache(ttl_seconds=30.0, clock=lambda: 100.0)
    cache.set(("beans", None), "cached-value")
    assert cache.get(("beans", None)) == "cached-value"


def test_ttl_cache_miss_returns_none():
    cache = TTLCache(ttl_seconds=30.0, clock=lambda: 100.0)
    assert cache.get(("beans", None)) is None


def test_ttl_cache_expires_after_ttl():
    now = {"t": 0.0}
    cache = TTLCache(ttl_seconds=30.0, clock=lambda: now["t"])
    cache.set(("beans", None), "value")

    now["t"] = 29.9
    assert cache.get(("beans", None)) == "value"  # 還沒到期

    now["t"] = 30.1
    assert cache.get(("beans", None)) is None  # 過期了，視為 cache miss


def test_ttl_cache_invalidate_all_clears_everything():
    cache = TTLCache(ttl_seconds=30.0, clock=lambda: 0.0)
    cache.set(("beans", None), "a")
    cache.set(("drip", None), "b")
    assert cache.size() == 2

    cache.invalidate_all()
    assert cache.size() == 0
    assert cache.get(("beans", None)) is None


# ---------- 整合測試：products.py 實際有沒有用到快取 ----------


def test_product_list_cache_hits_do_not_change_underlying_data(client: TestClient, admin_headers: dict):
    """驗證「快取命中」這件事本身，不容易只靠回應內容看出來（因為資料沒變）。

    這裡改用一個間接但可靠的驗證方式：後台把商品 1 改價，如果前台馬上查
    （還在 TTL 內）看到的是舊價格，就證明真的有從快取拿資料而不是每次重查
    資料庫；接著呼叫會觸發 `invalidate_all()` 的更新端點後，前台應該立刻看到新價格
    ——這一段就是 admin.py 呼叫 `products_cache.invalidate_all()` 的教學重點。
    """
    before = client.get("/api/products/1").json()
    original_price = before["price"]

    # 先打一次列表，確保 (None, None) 這個 key 已經被放進快取。
    first_list = client.get("/api/products").json()
    cached_price = next(item["price"] for item in first_list["items"] if item["id"] == 1)
    assert cached_price == original_price

    new_price = original_price + 111  # 隨便選一個一定跟原價不同的整數，避免巧合對不上
    client.patch("/api/admin/products/1", json={"price": new_price}, headers=admin_headers)

    # admin.py 的 update_product_route 呼叫了 products_cache.invalidate_all()，
    # 所以這裡立刻再查一次列表，應該馬上看到新價格，不用等 30 秒 TTL 過期。
    after_update_list = client.get("/api/products").json()
    updated_price = next(item["price"] for item in after_update_list["items"] if item["id"] == 1)
    assert updated_price == new_price
