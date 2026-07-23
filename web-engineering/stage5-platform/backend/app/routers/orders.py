"""
訂單路由——/api/orders*：從購物車建立訂單、查詢自己的訂單列表與詳情、取消訂單。

跟 stage4 最重要的差異——「建單不再扣庫存」：stage4 沒有付款概念，下單本身就是
唯一的「確定要買」動作，所以只能在建單當下扣庫存；本階段有了 `/api/payments/mock`
（見 routers/payments.py），「確定要買」跟「錢真的付了」變成兩個不同的時間點，
如果還是在建單當下扣庫存，會出現「使用者建了單、卻一直不付款」的訂單長期佔用
庫存、其他人明明想買卻買不到的問題（購物車囤貨的簡化版風險）。所以本階段改成
「建單只保留商品快照（名稱/價格），真正的扣庫存動作延後到付款成功那一刻」，
理由與完整取捨寫在 docs/DATABASE.md「訂單狀態與扣庫存時機」一節。

新增 `POST /api/orders/{id}/cancel`：只有本人、且訂單還是 pending 狀態才能取消
（用 app/order_state.py 的 `can_customer_cancel` 判斷），非法狀態轉移回 409。
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.db.database import (
    clear_cart,
    create_order,
    get_cart_items,
    get_order_by_id,
    get_product_by_id,
    list_orders_by_user,
    update_order_status,
)
from app.deps import get_current_user, get_db
from app.order_state import can_customer_cancel
from app.schemas import SQLITE_INT64_MAX, OrderCreateIn, OrderDetailOut, OrderListOut, OrderSummaryOut

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.post("", response_model=OrderDetailOut, status_code=status.HTTP_201_CREATED)
def create_order_route(
    payload: OrderCreateIn,
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> OrderDetailOut:
    user_id = current_user["id"]
    cart_items = get_cart_items(conn, user_id)
    if not cart_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="購物車是空的")

    # 用「當下最新」的商品資料做快照（名稱、價格），而不是直接沿用購物車裡可能已經
    # 過時的資料——購物車跟建單之間可能隔了一段時間，商品價格可能變動過。
    # 這裡刻意不檢查庫存、也不扣庫存（跟 stage4 最大的差異，見檔案開頭說明）：
    # 建單只是「我想買這些東西」的意思表示，真正動用到庫存要等到付款成功。
    order_items: list[dict] = []
    for cart_item in cart_items:
        product = get_product_by_id(conn, cart_item["product_id"])
        if product is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="購物車內有商品已下架")

        order_items.append(
            {
                "product_id": product["id"],
                "product_name": product["name"],
                "unit_price": product["price"],
                "quantity": cart_item["quantity"],
            }
        )

    total_amount = sum(item["unit_price"] * item["quantity"] for item in order_items)
    order_id = create_order(
        conn,
        user_id=user_id,
        total_amount=total_amount,
        recipient_name=payload.recipient_name,
        recipient_address=payload.recipient_address,
        items=order_items,
    )
    # 建單成功後清空購物車——這筆購物車內容已經「轉換」成訂單了，不應該還留著。
    clear_cart(conn, user_id)

    order = get_order_by_id(conn, order_id, user_id)
    return OrderDetailOut(**order)


@router.get("", response_model=OrderListOut)
def list_orders_route(
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> OrderListOut:
    orders = list_orders_by_user(conn, current_user["id"])
    return OrderListOut(items=[OrderSummaryOut(**order) for order in orders])


@router.get("/{order_id}", response_model=OrderDetailOut)
def get_order_route(
    # 上限對齊 SQLite INTEGER 欄位的 64-bit 範圍，理由見 app/schemas.py
    # `SQLITE_INT64_MAX` 的說明。
    order_id: int = Path(ge=1, le=SQLITE_INT64_MAX),
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> OrderDetailOut:
    order = get_order_by_id(conn, order_id, current_user["id"])
    if order is None:
        # 別人的訂單一律回 404（不是 403），避免洩漏「這個訂單 id 存在，只是不是你的」。
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到這筆訂單")
    return OrderDetailOut(**order)


@router.post("/{order_id}/cancel", response_model=OrderDetailOut)
def cancel_order_route(
    # 上限對齊 SQLite INTEGER 欄位的 64-bit 範圍，理由見 app/schemas.py
    # `SQLITE_INT64_MAX` 的說明。
    order_id: int = Path(ge=1, le=SQLITE_INT64_MAX),
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> OrderDetailOut:
    order = get_order_by_id(conn, order_id, current_user["id"])
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到這筆訂單")
    if not can_customer_cancel(order["status"]):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"訂單目前狀態是「{order['status']}」，無法由顧客自行取消",
        )
    update_order_status(conn, order_id, "cancelled")
    updated = get_order_by_id(conn, order_id, current_user["id"])
    return OrderDetailOut(**updated)
