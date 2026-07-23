"""
模擬付款路由——/api/payments/mock：本教案「金流」的核心，完全不接任何外部服務。

在真實世界的金流（例如 PayUNI、Stripe）裡，這一步會呼叫第三方 API、處理
webhook/callback、驗證簽章；這裡全部用「卡號規則」在本機模擬，方便學員不用
申請任何金流帳號就能跑完整個購買流程。

固定規則（不得更改，對應前端測試卡號說明）：
- 卡號 4000 0000 0000 0002 → 一律模擬「付款失敗」（模擬銀行端餘額不足）。
- 其他任何 16 碼卡號（示範用 4242 4242 4242 4242）→ 一律模擬「付款成功」。

教學點——為什麼「付款成功才扣庫存」，還要在扣庫存前重新檢查一次庫存：
下單（POST /api/orders）當下沒有鎖庫存，付款成功的這一刻才是「真的要把貨保留給
這個人」的時間點，所以要在這裡重新確認庫存還夠不夠；不夠的話，這筆付款就不能算
成功（就算卡號規則判斷起來「應該」要成功），要讓訂單變成 failed，並讓顧客知道
「不是卡的問題，是商品剛好被搶完了」。
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import Repos, get_current_user, get_repos
from app.schemas import OrderBriefOut, PaymentMockIn, PaymentMockOut, PaymentOut

router = APIRouter(prefix="/api/payments", tags=["payments"])

# 這組卡號是教學專案裡「唯一」會模擬失敗的卡號，其餘一律視為成功。
FAILING_CARD_NUMBER = "4000000000000002"


@router.post("/mock", response_model=PaymentMockOut)
def mock_payment(
    payload: PaymentMockIn,
    current_user: dict = Depends(get_current_user),
    repos: Repos = Depends(get_repos),
) -> PaymentMockOut:
    user_id = current_user["id"]
    order = repos.orders.get_by_id(payload.order_id, user_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到這筆訂單")

    if order["status"] == "paid":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="這筆訂單已經付款完成"
        )
    # 注意：pending 跟 failed 都可以重新呼叫這支付款 API（失敗訂單可以重試付款），
    # 只有 paid／cancelled 才擋下來。目前專案沒有任何端點會把訂單狀態設成
    # cancelled（屬於 forward-looking 防呆），但訊息文案要跟實際狀態對應——
    # 「已取消」跟「已付款完成」是完全不同的情境，不能共用同一句話，
    # 否則使用者會被誤導以為自己其實已經付過款了。
    if order["status"] == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="這筆訂單已經取消，無法再付款"
        )
    if order["status"] not in ("pending", "failed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="這筆訂單已經付款完成"
        )

    card_last4 = payload.card_number[-4:]
    transaction_id = f"MOCK-{uuid.uuid4()}"

    if payload.card_number == FAILING_CARD_NUMBER:
        # 模擬銀行端拒絕交易：記一筆失敗的付款紀錄、訂單狀態退回/停在 failed，
        # 顧客可以帶著同一張訂單再打一次這支 API 重試（換一張卡，或修正資料）。
        repos.orders.add_payment(
            order_id=order["id"],
            amount=order["total_amount"],
            status="failed",
            transaction_id=transaction_id,
            card_last4=card_last4,
        )
        repos.orders.update_status(order["id"], "failed")
        return PaymentMockOut(
            payment=PaymentOut(
                transaction_id=transaction_id,
                status="failed",
                amount=order["total_amount"],
                card_last4=card_last4,
            ),
            order=OrderBriefOut(id=order["id"], status="failed"),
        )

    # 卡號規則判斷「應該成功」，但付款當下要重新確認庫存還夠——
    # 這裡採用「先把每一項都檢查過一輪，全部都夠才真正逐項扣減」的做法：
    # 一次把「哪些商品不夠」都排除掉，才開始真正扣庫存，避免扣到一半才發現某一項不夠、
    # 前面已經扣掉的庫存還要想辦法補回去的麻煩。
    # 注意（已知簡化）：檢查跟扣減仍然是兩個分開的步驟，在極端高並發情況下，
    # 這兩步之間理論上還是有極小的競爭空間；`decrease_stock()` 本身的條件式 UPDATE
    # 才是真正保證單一商品不超賣的最後一道防線。
    for item in order["items"]:
        product = repos.products.get_by_id(item["product_id"])
        if product is None or product["stock"] < item["quantity"]:
            repos.orders.add_payment(
                order_id=order["id"],
                amount=order["total_amount"],
                status="failed",
                transaction_id=transaction_id,
                card_last4=card_last4,
            )
            repos.orders.update_status(order["id"], "failed")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="庫存不足，無法完成付款"
            )

    for item in order["items"]:
        # 教學點——為什麼一定要檢查 decrease_stock() 的回傳值，不能呼叫完就當作成功：
        # base.py 的 ProductRepository.decrease_stock() 明確定義「回傳是否扣成功」，
        # 就是設計給呼叫端在這裡判斷用的。上面的檢查迴圈跟這裡的扣減迴圈之間仍有
        # 時間差（尤其 DB_BACKEND=supabase 時每次 decrease_stock 都是一次獨立的
        # HTTP 往返，視窗比 SQLite 同 process 內呼叫寬得多），如果庫存在這段時間
        # 被別的並發付款搶走，decrease_stock() 會回傳 False（沒有任何一列被更新），
        # 這時如果不檢查、繼續無條件把訂單標記 paid，就會出現「顧客被收了錢、
        # 訂單顯示付款成功，但商品實際上完全沒扣到庫存」的帳目對不上的嚴重問題。
        # 已知簡化：這裡採用「一有任一項目扣減失敗就整筆訂單標記失敗」，但前面
        # 已經扣成功的品項**不會自動補回**（沒有實作 rollback／補償邏輯）；
        # 正式系統會需要用資料庫交易或補償機制處理這個殘留風險，教學上先誠實
        # 揭露這個已知限制。
        success = repos.products.decrease_stock(item["product_id"], item["quantity"])
        if not success:
            repos.orders.add_payment(
                order_id=order["id"],
                amount=order["total_amount"],
                status="failed",
                transaction_id=transaction_id,
                card_last4=card_last4,
            )
            repos.orders.update_status(order["id"], "failed")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="庫存不足，無法完成付款"
            )

    repos.orders.add_payment(
        order_id=order["id"],
        amount=order["total_amount"],
        status="success",
        transaction_id=transaction_id,
        card_last4=card_last4,
    )
    repos.orders.update_status(order["id"], "paid")

    return PaymentMockOut(
        payment=PaymentOut(
            transaction_id=transaction_id,
            status="success",
            amount=order["total_amount"],
            card_last4=card_last4,
        ),
        order=OrderBriefOut(id=order["id"], status="paid"),
    )
