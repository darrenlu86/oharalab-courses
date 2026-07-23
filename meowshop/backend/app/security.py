"""
安全層（security layer）——密碼雜湊與 JWT token 的產生/解析。

負責什麼：
1. 密碼處理：只提供 `hash_password()` / `verify_password()` 兩個函式，
   全專案任何地方都不會出現明文密碼比對或明文密碼儲存。
2. Token 處理：`create_access_token()` 簽發 JWT，`decode_access_token()` 驗證並解開 JWT。

在架構中的位置：介於「路由層」與「使用者資料」之間的工具層，不直接碰資料庫，
純粹是密碼學/編碼的邏輯，方便單獨測試、也方便以後抽換演算法。

關鍵設計「為什麼」：

- 為什麼用 bcrypt 而不是自己寫雜湊：bcrypt 會自動幫每筆密碼加上獨立的隨機 salt，
  就算兩個使用者密碼一樣，存出來的 hash 也不同，可以防止「rainbow table」查表攻擊。
  這也是為什麼 SPEC 明確指定用 bcrypt 而不是 MD5/SHA256 直接雜湊密碼。
- 為什麼用 JWT 而不是 session：JWT 是「自包含」的憑證，伺服器不需要另外存一份
  「誰登入了」的 session 表，天生適合多台伺服器水平擴充。
  注意（初學者常見誤解）：JWT 一旦簽出去，在到期前**沒辦法主動撤銷**
  （除非額外做一個黑名單機制）。所以這裡把過期時間設得比較短（24 小時），
  是「安全性」與「使用者不用一直重新登入」之間的折衷。
- 為什麼 payload 放 user id 而不是整包 user 資料：JWT 內容任何人都能用 base64 解開看到
  （雖然改不了，因為有簽章），所以絕對不能把密碼雜湊等敏感資料放進 payload。
  這裡只放最小必要資訊（user id），其餘使用者資料每次都重新從資料庫查，
  確保拿到的永遠是最新的（例如帳號被停用時，可以即時反映）。
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import get_settings

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24


def hash_password(password: str) -> str:
    """把明文密碼雜湊成可以安全存進資料庫的字串。"""
    # 注意（最後一道防線，不是第一道）：bcrypt 演算法本身有 72 bytes 的密碼長度
    # 上限，超過的話 bcrypt.hashpw() 會丟 ValueError；正常流程下這個情況早就該在
    # schemas.py 的 UserCreate.password 驗證器被擋下來（變成乾淨的 422），
    # 不應該走到這裡。這裡仍然多做一層檢查，是因為 hash_password() 是可以被
    # 任何程式碼直接呼叫的公用函式（例如以後寫 CLI 工具、批次腳本重設密碼），
    # 不能假設呼叫端一定會先經過 FastAPI 的 schema 驗證；寧可在這裡明確
    # raise 一個好懂的 ValueError，也不要讓 bcrypt 的原始例外訊息外洩到呼叫端。
    if len(password.encode("utf-8")) > 72:
        raise ValueError("密碼太長：最長 72 個位元組（bcrypt 演算法的限制）")
    # bcrypt.gensalt() 每次呼叫都會產生新的隨機 salt，這就是「就算密碼一樣、
    # hash 結果也不同」的關鍵。password 要先 encode 成 bytes，bcrypt 才吃得下。
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """驗證使用者輸入的明文密碼，是否和資料庫存的雜湊值相符。"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # 注意：如果資料庫裡存的不是合法的 bcrypt hash（例如資料髒了），
        # bcrypt.checkpw 會丟 ValueError；這裡把它視為「驗證失敗」而不是讓整個
        # request 500 錯誤，對使用者來說體驗一致（都是「帳密錯誤」）。
        return False


def create_access_token(user_id: int, email: str) -> str:
    """簽發一個 24 小時後過期的 JWT，payload 只放最小必要資訊。"""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),  # sub = subject，JWT 慣例用法，代表這個 token 是關於誰的
        "email": email,
        "iat": now,  # issued at：簽發時間
        "exp": now + timedelta(hours=TOKEN_EXPIRE_HOURS),  # expire：過期時間
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """解開並驗證 JWT。過期或簽章不對都會丟出 `jwt` 套件的例外，交給呼叫端處理成 401。"""
    settings = get_settings()
    # jwt.decode 預設就會檢查 exp 是否過期、簽章是否正確，不需要我們手動比對時間。
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
