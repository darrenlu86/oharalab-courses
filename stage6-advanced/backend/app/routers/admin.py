"""
後台管理路由——`/api/admin/*`：本階段新增的模組，stage4 完全沒有後台。

全部端點都掛 `require_admin`（見 app/deps.py），沒帶 token → 401；帶了 token 但
不是 admin 角色 → 403；權限矩陣完整表格見 docs/SYSTEM_DESIGN.md。

四大功能：
1. `GET /summary`：儀表板數字——真實 SQL 聚合（見 app/db/database.py 的 admin_summary()），
   不是前端自己把訂單清單拉下來加總，教學點是「聚合運算能交給資料庫做就交給資料庫做」。
2. 商品 CRUD（新增／編輯／上下架）：`POST /products`、`PATCH /products/{id}`。
   刻意不提供刪除——見 app/db/database.py `update_product()` 與 schema.sql 的說明，
   下架（is_active=0）保留歷史訂單品項快照的完整性，真正的 DELETE 沒有這個保證。
   **stage6 新增**：商品新增/編輯成功後呼叫 `products_cache.invalidate_all()`
   （見 app/cache.py），確保後台一改完商品，前台下一次 `GET /api/products`
   不會繼續看到 TTL 還沒過期的舊資料——這是「cache invalidation」在本專案
   最直接的示範：快取的價值來自「減少查資料庫的次數」，但代價是「資料改變時
   必須記得通知快取」，這裡選擇最保守的作法（整包清空），理由見 cache.py。
3. 訂單管理：`GET /orders`（可用 status 篩選，stage6 改用單次 JOIN 查詢，見
   app/db/database.py `list_all_orders()` 的 N+1 修復說明）、
   `PATCH /orders/{id}/status`（只接受 app/order_state.py 定義的合法轉移，
   非法轉移一律 409）。**stage6 新增**：狀態更新成功後透過 WebSocket 廣播給
   所有連線的後台管理員，也推播給該訂單所屬顧客本人（見 app/ws_manager.py），
   前台/後台都不用重新整理就能看到最新狀態。
4. 會員清單：`GET /users`——不含密碼欄位（list_users() 在 SQL 層就沒有 SELECT
   password_hash，見 database.py 的說明），同樣不提供刪除（隱私保護：使用者的
   歷史訂單需要保留 user_id 才能對帳，直接刪除帳號會破壞這個關聯，正式產品的
   作法是「停用帳號」而非刪除，這裡教學上只示範「唯讀清單」）。
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.cache import products_cache
from app.db.database import (
    admin_summary,
    create_product,
    get_order_by_id_any_user,
    get_product_by_id,
    list_all_orders,
    list_products,
    list_users,
    update_order_status,
    update_product,
)
from app.deps import get_db, require_admin
from app.order_state import is_admin_transition_allowed
from app.schemas import (
    SQLITE_INT64_MAX,
    AdminOrderListOut,
    AdminOrderOut,
    AdminSummaryOut,
    AdminUserListOut,
    AdminUserOut,
    OrderStatusUpdateIn,
    ProductAdminCreateIn,
    ProductAdminUpdateIn,
    ProductListOut,
    ProductOut,
)
from app.ws_manager import manager

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/summary", response_model=AdminSummaryOut)
def summary_route(conn: sqlite3.Connection = Depends(get_db)) -> AdminSummaryOut:
    data = admin_summary(conn)
    return AdminSummaryOut(**data)


# ---------- 商品 ----------


@router.get("/products", response_model=ProductListOut)
def list_products_route(conn: sqlite3.Connection = Depends(get_db)) -> ProductListOut:
    """後台商品列表——`include_inactive=True`，連已下架的商品也列出來，這樣管理員
    才找得到「哪些商品已經下架、要不要重新上架」；前台的 `GET /api/products`
    永遠只看得到上架商品，兩者刻意分開（見 app/db/database.py `list_products()`
    的 `include_inactive` 參數說明）。"""
    items = list_products(conn, include_inactive=True)
    return ProductListOut(items=[ProductOut(**item) for item in items], total=len(items))


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product_route(
    payload: ProductAdminCreateIn, conn: sqlite3.Connection = Depends(get_db)
) -> ProductOut:
    product = create_product(
        conn,
        name=payload.name,
        description=payload.description,
        price=payload.price,
        stock=payload.stock,
        category=payload.category,
        image_url=payload.image_url,
    )
    products_cache.invalidate_all()
    return ProductOut(**product)


@router.patch("/products/{product_id}", response_model=ProductOut)
def update_product_route(
    payload: ProductAdminUpdateIn,
    # 上限對齊 SQLite INTEGER 欄位的 64-bit 範圍，理由見 app/schemas.py
    # `SQLITE_INT64_MAX` 的說明。
    product_id: int = Path(ge=1, le=SQLITE_INT64_MAX),
    conn: sqlite3.Connection = Depends(get_db),
) -> ProductOut:
    existing = get_product_by_id(conn, product_id, include_inactive=True)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到這個商品")

    fields = payload.model_dump(exclude_unset=True, exclude_none=True)
    updated = update_product(conn, product_id, fields)
    products_cache.invalidate_all()
    return ProductOut(**updated)


# ---------- 訂單 ----------


@router.get("/orders", response_model=AdminOrderListOut)
def list_orders_route(
    order_status: str | None = None, conn: sqlite3.Connection = Depends(get_db)
) -> AdminOrderListOut:
    orders = list_all_orders(conn, status=order_status)
    return AdminOrderListOut(items=[AdminOrderOut(**order) for order in orders])


@router.patch("/orders/{order_id}/status", response_model=AdminOrderOut)
async def update_order_status_route(
    payload: OrderStatusUpdateIn,
    # 上限對齊 SQLite INTEGER 欄位的 64-bit 範圍，理由見 app/schemas.py
    # `SQLITE_INT64_MAX` 的說明。
    order_id: int = Path(ge=1, le=SQLITE_INT64_MAX),
    conn: sqlite3.Connection = Depends(get_db),
) -> AdminOrderOut:
    order = get_order_by_id_any_user(conn, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到這筆訂單")

    if not is_admin_transition_allowed(order["status"], payload.status):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"不允許從「{order['status']}」轉換成「{payload.status}」",
        )

    update_order_status(conn, order_id, payload.status)
    updated = get_order_by_id_any_user(conn, order_id)
    updated_out = AdminOrderOut(**updated)

    # stage6 新增：狀態改變後同時廣播給所有後台管理員（讓其他分頁/其他管理員
    # 也立刻看到）以及這筆訂單的顧客本人（見 app/ws_manager.py 的頻道說明）。
    # 這支路由因此改成 `async def`——`await manager.xxx()` 需要在一個
    # coroutine 裡才能呼叫，這是本階段把「原本是 sync 的路由」改成 async 的
    # 唯一理由，不是為了效能（sqlite3 操作本身仍然是同步、會擋住事件迴圈，
    # 見 docs/ARCHITECTURE.md「uvicorn workers」一節對這個取捨的完整討論）。
    event = {"type": "order_status_changed", "order": updated_out.model_dump()}
    await manager.broadcast_admin(event)
    await manager.send_to_user(updated["user_id"], event)

    return updated_out


# ---------- 會員 ----------


@router.get("/users", response_model=AdminUserListOut)
def list_users_route(conn: sqlite3.Connection = Depends(get_db)) -> AdminUserListOut:
    users = list_users(conn)
    return AdminUserListOut(items=[AdminUserOut(**user) for user in users])
