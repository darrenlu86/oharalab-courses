"""
訂單路由——/api/orders*：從購物車建立訂單、查詢自己的訂單列表與詳情。

教學重點——「建單當下直接扣庫存」，跟 meowshop「付款成功才扣庫存」不同：
本階段還沒有付款概念（沒有 payments 路由、沒有金流），下單本身就是唯一的
「確定要買」動作，所以扣庫存的時機只能選在建單當下，不像 meowshop 有「建單」
跟「付款」兩個時間點可以選——這個取捨、以及它帶來的限制，寫在 docs/DATABASE.md
「訂單狀態與扣庫存時機」一節，這裡不重複，只講程式碼層面怎麼做到「安全地扣庫存」。

**多品項扣庫存的原子性**：一筆訂單可能含好幾件商品，如果扣到一半才發現某件
庫存不夠，不能留下「前面幾件已經扣了、後面沒扣、但訂單也沒建立」的中間狀態。
做法是全部操作都在同一條連線（`conn`，由 `get_db` 這個 request-scoped dependency
提供）上進行、最後才一次 `conn.commit()`；只要中途任何一件商品扣庫存失敗，
就呼叫 `conn.rollback()` 把這條連線上「還沒 commit」的所有變更全部撤銷，
確保「全部成功」或「完全不變」，不會出現扣了一半的中間狀態。
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.db.database import (
    clear_cart,
    create_order,
    decrease_stock,
    get_cart_items,
    get_order_by_id,
    get_product_by_id,
    list_orders_by_user,
)
from app.deps import get_current_user, get_db
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
    # 這裡跟扣庫存共用同一個迴圈：只要有一項庫存不夠，整條連線立刻 rollback，
    # 不留下「前面幾件已經扣了、這件沒扣、訂單也沒建立」的中間狀態。
    order_items: list[dict] = []
    for cart_item in cart_items:
        product = get_product_by_id(conn, cart_item["product_id"])
        if product is None:
            conn.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="購物車內有商品已下架")

        ok = decrease_stock(conn, product["id"], cart_item["quantity"])
        if not ok:
            conn.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"庫存不足，目前只剩 {product['stock']} 件",
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
    order_id = create_order(
        conn,
        user_id=user_id,
        total_amount=total_amount,
        recipient_name=payload.recipient_name,
        recipient_address=payload.recipient_address,
        items=order_items,
    )
    # 建單成功後清空購物車——這筆購物車內容已經「轉換」成訂單了，不應該還留著。
    # clear_cart 內部有自己的 commit()，但那個 commit 只會真的落地已扣過庫存 +
    # 已建立訂單的這整條連線變更，因為 SQLite 一條連線上的所有未提交寫入
    # 是一起被 commit 的，不會被拆開。
    clear_cart(conn, user_id)
    conn.commit()

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
