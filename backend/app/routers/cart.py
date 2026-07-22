"""
購物車路由——/api/cart*：全部端點都需要登入（掛 `get_current_user` 依賴）。

設計重點：購物車的「總計」（total_amount / total_quantity）跟每項的「小計」
（subtotal）都是在這一層即時算出來的，資料庫並不會存這些衍生值——
教學點：能夠從其他欄位算出來的值，就不要重複存進資料庫，否則商品改價後，
購物車裡存的小計就會跟商品現價對不上，變成兩份「真相」互相打架。
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import Repos, get_current_user, get_repos
from app.schemas import CartItemIn, CartItemOut, CartOut, CartQuantityIn

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
def get_cart(
    current_user: dict = Depends(get_current_user),
    repos: Repos = Depends(get_repos),
) -> CartOut:
    raw_items = repos.carts.get_items(current_user["id"])
    return _build_cart_out(raw_items)


@router.post("/items", response_model=CartOut)
def add_item(
    payload: CartItemIn,
    current_user: dict = Depends(get_current_user),
    repos: Repos = Depends(get_repos),
) -> CartOut:
    product = repos.products.get_by_id(payload.product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到這個商品")

    # 「已經在購物車內」要用累加，所以先算出「加進去之後總共會有幾件」，
    # 拿這個總數跟庫存比較，而不是只拿這次新加的數量比較。
    existing_items = repos.carts.get_items(current_user["id"])
    existing_qty = next(
        (item["quantity"] for item in existing_items if item["product_id"] == payload.product_id),
        0,
    )
    total_after_add = existing_qty + payload.quantity
    if total_after_add > product["stock"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"庫存不足，目前只剩 {product['stock']} 件",
        )

    repos.carts.upsert_item(current_user["id"], payload.product_id, payload.quantity)
    return _build_cart_out(repos.carts.get_items(current_user["id"]))


@router.patch("/items/{product_id}", response_model=CartOut)
def update_item_quantity(
    product_id: int,
    payload: CartQuantityIn,
    current_user: dict = Depends(get_current_user),
    repos: Repos = Depends(get_repos),
) -> CartOut:
    product = repos.products.get_by_id(product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到這個商品")
    if payload.quantity > product["stock"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"庫存不足，目前只剩 {product['stock']} 件",
        )

    updated = repos.carts.set_quantity(current_user["id"], product_id, payload.quantity)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="購物車裡沒有這個商品"
        )
    return _build_cart_out(repos.carts.get_items(current_user["id"]))


@router.delete("/items/{product_id}", response_model=CartOut)
def remove_item(
    product_id: int,
    current_user: dict = Depends(get_current_user),
    repos: Repos = Depends(get_repos),
) -> CartOut:
    removed = repos.carts.remove_item(current_user["id"], product_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="購物車裡沒有這個商品"
        )
    return _build_cart_out(repos.carts.get_items(current_user["id"]))
