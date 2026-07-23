"""
商品路由——/api/products*：商品清單（分類篩選＋關鍵字搜尋）與商品詳情，不需要登入。

跟 stage4 的差異：`list_products` / `get_product_by_id` 都改用預設值
`include_inactive=False`，前台只看得到 `is_active=1` 的商品——下架商品的詳情頁
一律回 404（跟「商品根本不存在」用同一個狀態碼與訊息，不讓使用者分辨「這個
id 是不存在還是被下架」，理由跟訂單「別人的訂單也回 404」是同一套教學點）。
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.db.database import get_product_by_id, list_products
from app.deps import get_db
from app.schemas import SQLITE_INT64_MAX, ProductListOut, ProductOut

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=ProductListOut)
def list_products_route(
    category: str | None = None,
    search: str | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> ProductListOut:
    items = list_products(conn, category=category, search=search)
    return ProductListOut(items=[ProductOut(**item) for item in items], total=len(items))


@router.get("/{product_id}", response_model=ProductOut)
def get_product_route(
    # 上限對齊 SQLite INTEGER 欄位的 64-bit 範圍，理由見 app/schemas.py
    # `SQLITE_INT64_MAX` 的說明。
    product_id: int = Path(ge=1, le=SQLITE_INT64_MAX),
    conn: sqlite3.Connection = Depends(get_db),
) -> ProductOut:
    product = get_product_by_id(conn, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到這個商品")
    return ProductOut(**product)
