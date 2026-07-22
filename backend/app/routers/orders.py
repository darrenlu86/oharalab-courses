"""
訂單路由——/api/orders*：從購物車建立訂單、查詢自己的訂單列表與詳情。

教學重點——「建單不扣庫存，付款才扣庫存」：
下單的當下只是「登記這筆意向」，真正的庫存扣減發生在 /api/payments/mock
付款成功的那一刻（見 routers/payments.py）。

為什麼要這樣設計（trade-off）：
- 好處：如果顧客下單後臨時反悔、或付款一直沒完成，商品庫存不會被「卡住」，
  其他人還是買得到，避免大量「建了單但沒付錢」的訂單把熱門商品的庫存鎖光。
- 壞處（超賣風險）：如果同一件庫存只剩 1 件、兩個人都成功建立了訂單
  （建單當下只檢查、不鎖庫存），最後只有先付款的那個人能真的扣到庫存，
  後付款的人會在付款那一步收到「庫存不足」。這是簡化版設計的已知風險，
  正式電商常見的進階做法是「建單當下就『預留』庫存，付款/取消時再釋放」，
  這個進階題留給有興趣的學員自己延伸。
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import Repos, get_current_user, get_repos
from app.schemas import OrderCreateIn, OrderDetailOut, OrderListOut, OrderSummaryOut

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.post("", response_model=OrderDetailOut, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreateIn,
    current_user: dict = Depends(get_current_user),
    repos: Repos = Depends(get_repos),
) -> OrderDetailOut:
    user_id = current_user["id"]
    cart_items = repos.carts.get_items(user_id)
    if not cart_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="購物車是空的")

    # 用「當下最新」的商品資料做快照（名稱、價格），而不是直接沿用購物車裡
    # 可能已經過時的資料——購物車跟建單之間可能隔了一段時間，商品價格可能變動過。
    order_items: list[dict] = []
    for cart_item in cart_items:
        product = repos.products.get_by_id(cart_item["product_id"])
        if product is None or cart_item["quantity"] > product["stock"]:
            stock = product["stock"] if product else 0
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"庫存不足，目前只剩 {stock} 件",
            )
        order_items.append(
            {
                "product_id": product["id"],
                "product_name": product["name"],
                "unit_price": product["price"],
                "quantity": cart_item["quantity"],
            }
        )

    total_amount = sum(item["unit_price"] * item["quantity"] for item in order_items)
    order = repos.orders.create(
        user_id=user_id,
        total_amount=total_amount,
        recipient_name=payload.recipient_name,
        recipient_address=payload.recipient_address,
        items=order_items,
    )
    # 建單成功後清空購物車——這筆購物車內容已經「轉換」成訂單了，不應該還留著。
    repos.carts.clear(user_id)
    return OrderDetailOut(**order)


@router.get("", response_model=OrderListOut)
def list_orders(
    current_user: dict = Depends(get_current_user),
    repos: Repos = Depends(get_repos),
) -> OrderListOut:
    orders = repos.orders.list_by_user(current_user["id"])
    return OrderListOut(items=[OrderSummaryOut(**order) for order in orders])


@router.get("/{order_id}", response_model=OrderDetailOut)
def get_order(
    order_id: int,
    current_user: dict = Depends(get_current_user),
    repos: Repos = Depends(get_repos),
) -> OrderDetailOut:
    order = repos.orders.get_by_id(order_id, current_user["id"])
    if order is None:
        # 注意（教學安全點）：這裡刻意回 404 而不是 403。
        # 如果對「別人的訂單」回 403 Forbidden，等於告訴攻擊者「這個訂單 id 確實存在，
        # 只是不是你的」；回 404 讓「不存在」跟「存在但不是你的」看起來一模一樣，
        # 不洩漏系統裡到底有沒有這筆資料，稱為避免「資源存在性外洩」。
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到這筆訂單")
    return OrderDetailOut(**order)
