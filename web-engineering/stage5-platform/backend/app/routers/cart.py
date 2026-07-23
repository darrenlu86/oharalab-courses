"""
購物車路由——/api/cart*：全部端點都需要登入。

設計重點：購物車的「總計」（total_amount / total_quantity）跟每項的「小計」
（subtotal）都是即時算出來的，資料庫不會存這些衍生值——能從其他欄位算出來的值，
就不要重複存進資料庫，否則商品改價後，購物車存的小計就會跟商品現價對不上。
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.db.database import (
    get_cart_items,
    get_product_by_id,
    remove_cart_item,
    set_cart_item_quantity,
    upsert_cart_item,
)
from app.deps import get_current_user, get_db
from app.schemas import SQLITE_INT64_MAX, CartItemIn, CartItemOut, CartOut, CartQuantityIn

router = APIRouter(prefix="/api/cart", tags=["cart"])


def _build_cart_out(raw_items: list[dict]) -> CartOut:
    items = [
        CartItemOut(
            product_id=item["product_id"],
            name=item["name"],
            price=item["price"],
            image_url=item["image_url"],
            quantity=item["quantity"],
            stock=item["stock"],
            is_active=item["is_active"],
            subtotal=item["price"] * item["quantity"],
        )
        for item in raw_items
    ]
    return CartOut(
        items=items,
        total_amount=sum(item.subtotal for item in items),
        total_quantity=sum(item.quantity for item in items),
    )


@router.get("", response_model=CartOut)
def get_cart_route(
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> CartOut:
    return _build_cart_out(get_cart_items(conn, current_user["id"]))


@router.post("/items", response_model=CartOut)
def add_item_route(
    payload: CartItemIn,
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> CartOut:
    product = get_product_by_id(conn, payload.product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到這個商品")

    # 已經在購物車內要用累加，所以先算出「加進去之後總共會有幾件」，
    # 拿這個總數跟庫存比較，而不是只拿這次新加的數量比較。
    existing_items = get_cart_items(conn, current_user["id"])
    existing_qty = next(
        (item["quantity"] for item in existing_items if item["product_id"] == payload.product_id), 0
    )
    total_after_add = existing_qty + payload.quantity
    if total_after_add > product["stock"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"庫存不足，目前只剩 {product['stock']} 件",
        )

    upsert_cart_item(conn, current_user["id"], payload.product_id, payload.quantity)
    return _build_cart_out(get_cart_items(conn, current_user["id"]))


@router.patch("/items/{product_id}", response_model=CartOut)
def update_item_quantity_route(
    payload: CartQuantityIn,
    # 上限對齊 SQLite INTEGER 欄位的 64-bit 範圍，理由見 app/schemas.py
    # `SQLITE_INT64_MAX` 的說明。
    product_id: int = Path(ge=1, le=SQLITE_INT64_MAX),
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> CartOut:
    product = get_product_by_id(conn, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到這個商品")
    if payload.quantity > product["stock"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"庫存不足，目前只剩 {product['stock']} 件",
        )

    updated = set_cart_item_quantity(conn, current_user["id"], product_id, payload.quantity)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="購物車裡沒有這個商品")
    return _build_cart_out(get_cart_items(conn, current_user["id"]))


@router.delete("/items/{product_id}", response_model=CartOut)
def remove_item_route(
    # 上限對齊 SQLite INTEGER 欄位的 64-bit 範圍，理由見 app/schemas.py
    # `SQLITE_INT64_MAX` 的說明。
    product_id: int = Path(ge=1, le=SQLITE_INT64_MAX),
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> CartOut:
    removed = remove_cart_item(conn, current_user["id"], product_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="購物車裡沒有這個商品")
    return _build_cart_out(get_cart_items(conn, current_user["id"]))
