"""商品路由——/api/products*：商品清單（分類篩選＋關鍵字搜尋）與商品詳情，不需要登入。"""

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
    # 上限對齊 SQLite INTEGER 欄位的 64-bit 範圍——超過這個範圍的路徑參數會被
    # FastAPI 擋在這裡回 422，不會有機會摸到資料庫層觸發 OverflowError（見
    # app/schemas.py `SQLITE_INT64_MAX` 的說明）。
    product_id: int = Path(ge=1, le=SQLITE_INT64_MAX),
    conn: sqlite3.Connection = Depends(get_db),
) -> ProductOut:
    product = get_product_by_id(conn, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到這個商品")
    return ProductOut(**product)
