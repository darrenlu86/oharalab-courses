"""
訂單狀態機——本階段新增的模組，stage4 完全沒有這個檔案（stage4 的訂單只有一種
狀態，不需要狀態機）。

完整的狀態圖（含圖示）見 docs/SYSTEM_DESIGN.md「訂單狀態機」一節，這裡只放
「合法轉移」的資料本身，讓 routers 層（payments.py / admin.py / orders.py）
都呼叫同一份規則，不會每個檔案各自寫一份、日後改規則漏改其中一處。

三種轉移各自對應不同的呼叫端，刻意分成三張表，而不是合成一張「萬用」表：
1. `PAYMENT_ALLOWED_FROM`：能不能嘗試付款，只看「目前狀態在不在這個集合裡」，
   結果（成功/失敗）由 routers/payments.py 決定要轉去 'paid' 還是 'failed'。
2. `ADMIN_STATUS_TRANSITIONS`：後台 `PATCH /api/admin/orders/{id}/status` 允許的
   (from, to) 組合——出貨、完成、（含 paid 訂單的）取消，都是「店家才能做」的操作。
3. `CUSTOMER_CANCEL_ALLOWED_FROM`：顧客自己能取消訂單的前提狀態——只有 pending
   （都還沒付錢，說取消就取消，沒有金流上的後果）；paid 之後的取消一律要 admin
   出面（教學簡化：不做退款，見 docs/SYSTEM_DESIGN.md「取消與退款」一節）。
"""

PAYMENT_ALLOWED_FROM = {"pending", "failed"}

CUSTOMER_CANCEL_ALLOWED_FROM = {"pending"}

ADMIN_STATUS_TRANSITIONS: set[tuple[str, str]] = {
    ("pending", "cancelled"),
    ("failed", "cancelled"),
    ("paid", "shipped"),
    ("paid", "cancelled"),
    ("shipped", "completed"),
}

ALL_STATUSES = ("pending", "paid", "failed", "shipped", "completed", "cancelled")


def is_admin_transition_allowed(current_status: str, target_status: str) -> bool:
    return (current_status, target_status) in ADMIN_STATUS_TRANSITIONS


def can_customer_cancel(current_status: str) -> bool:
    return current_status in CUSTOMER_CANCEL_ALLOWED_FROM


def can_attempt_payment(current_status: str) -> bool:
    return current_status in PAYMENT_ALLOWED_FROM
