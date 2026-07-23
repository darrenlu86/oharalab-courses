"""
付款路由——`POST /api/payments/mock`：本階段新增的模組，stage4 完全沒有付款功能。

跟 meowshop 的模擬金流是同一套規則（測試卡號表見 docs/API.md 與前台結帳頁）：
卡號 `4000000000000002` 一律視為失敗，其餘任何合法格式的卡號一律視為成功。
**這不是真的信用卡驗證，純粹是後端讀「卡號字串」做規則判斷，不會、也不可能
真的請款**——完整的金流警示聲明見 README.md 開頭與 docs/DEPLOY.md。

教學重點——「付款成功才扣庫存」：
stage4 在建單當下就扣庫存，因為那時候沒有「付款」這個中間狀態，下單就是唯一的
「確定要買」時刻。本階段有了付款流程，「使用者送出訂單」跟「這筆訂單真的成立」
之間可能隔著使用者猶豫、切換分頁、甚至直接放棄結帳的時間差，如果建單當下就扣
庫存，會出現一堆「下單但沒付」的訂單長期佔用庫存、其他人明明想買卻買不到
（庫存被卡住）的問題。所以本階段把扣庫存的時機明確移到「付款成功」這一刻，
「建單」單純只是「登記這筆意向、鎖住當下的商品名稱與價格」。

扣庫存與寫入 payments/orders 的原子性：先在同一條連線上把每個品項的庫存都扣完，
任何一項不夠就整個 `rollback()`（此時 payments 表跟 orders 表都還沒被這次付款
動到，訂單維持原本狀態，允許使用者之後重新嘗試付款）；全部扣成功才真正寫入
付款紀錄與訂單狀態。
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status

from app.db.database import (
    create_payment,
    decrease_stock,
    get_order_by_id,
    update_order_status,
)
from app.deps import get_current_user, get_db
from app.order_state import can_attempt_payment
from app.schemas import PaymentIn, PaymentResultOut

router = APIRouter(prefix="/api/payments", tags=["payments"])

# 唯一會「一律失敗」的測試卡號；其餘任何 13-19 碼數字（PaymentIn 已驗證過格式）
# 都視為成功——跟 meowshop 的測試卡規則一致，教學上只需要記一組會失敗的卡號即可。
FAILING_CARD_NUMBER = "4000000000000002"


@router.post("/mock", response_model=PaymentResultOut)
def mock_payment_route(
    payload: PaymentIn,
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> PaymentResultOut:
    order = get_order_by_id(conn, payload.order_id, current_user["id"])
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到這筆訂單")

    if not can_attempt_payment(order["status"]):
        if order["status"] == "cancelled":
            detail = "這筆訂單已經取消，無法付款"
        else:
            detail = "這筆訂單已經付款完成"
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    card_last4 = payload.card_number[-4:]

    if payload.card_number == FAILING_CARD_NUMBER:
        payment = create_payment(
            conn, order_id=order["id"], amount=order["total_amount"], card_last4=card_last4, status="failed"
        )
        update_order_status(conn, order["id"], "failed")
        updated_order = get_order_by_id(conn, order["id"], current_user["id"])
        return PaymentResultOut(payment=payment, order=updated_order)

    # 付款成功：這裡才是真正扣庫存的時間點（見檔案開頭說明）。多品項訂單要嘛
    # 全部扣成功、要嘛完全不動，理由跟 stage4 建單時的原子性設計一致。
    for item in order["items"]:
        ok = decrease_stock(conn, item["product_id"], item["quantity"])
        if not ok:
            conn.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"「{item['product_name']}」庫存不足，付款未完成，請調整數量後重新建立訂單",
            )
    conn.commit()

    payment = create_payment(
        conn, order_id=order["id"], amount=order["total_amount"], card_last4=card_last4, status="success"
    )
    update_order_status(conn, order["id"], "paid")
    updated_order = get_order_by_id(conn, order["id"], current_user["id"])
    return PaymentResultOut(payment=payment, order=updated_order)
