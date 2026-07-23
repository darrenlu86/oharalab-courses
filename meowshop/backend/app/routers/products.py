"""
商品路由——/api/products*：商品清單（含分類篩選、關鍵字搜尋）與商品詳情。

這兩支端點都不需要登入，任何人都可以瀏覽商品，符合一般電商「先逛後買」的體驗。
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import Repos, get_repos
from app.schemas import ProductListOut, ProductOut

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=ProductListOut)
def list_products(
    category: str | None = None,
    search: str | None = None,
    repos: Repos = Depends(get_repos),
) -> ProductListOut:
    items = repos.products.list(category=category, search=search)
    return ProductListOut(items=[ProductOut(**item) for item in items], total=len(items))


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, repos: Repos = Depends(get_repos)) -> ProductOut:
    product = repos.products.get_by_id(product_id)
    if product is None:
        # 找不到跟「已下架」用同一個訊息——對顧客來說兩種情況的體驗應該一樣：
        # 這個商品現在就是看不到、買不到，不需要區分背後原因。
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到這個商品")
    return ProductOut(**product)
