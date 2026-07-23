"""
依賴注入層（FastAPI dependencies）。

負責什麼：提供兩個給 routers 用 `Depends()` 掛載的共用邏輯——
1. `get_repos`：組出這次 request 要用的一組 Repository（呼叫 factory.py）。
2. `get_current_user`：解析 `Authorization: Bearer <token>`，驗證 JWT，
   查出目前登入的使用者，任何「需要登入」的端點都掛這個依賴即可。

為什麼把「驗證 token」寫成一個 dependency，而不是每個路由函式自己複製貼上：
FastAPI 的 dependency 可以在多個路由之間共用，也會自動反映在 `/docs` 的
「這個端點需要授權」標示上；改天要調整「怎樣算登入」的邏輯（例如加上黑名單機制），
只需要改這一個函式。
"""

from fastapi import Depends, Header, HTTPException, status

from app.repositories.factory import Repos, get_repositories
from app.security import decode_access_token


def get_repos() -> Repos:
    return get_repositories()


def get_current_user(
    authorization: str | None = Header(default=None),
    repos: Repos = Depends(get_repos),
) -> dict:
    """解析 Bearer token，回傳目前登入的使用者 dict；驗證失敗一律回 401「請先登入」。

    注意：不管是「完全沒帶 token」「格式不對」「token 過期」還是「token 對應的
    使用者已經不存在」，回傳的錯誤訊息都刻意統一成同一句「請先登入」——
    不要對外區分「你的 token 過期了」跟「你的 token 是假的」，這是避免洩漏
    系統內部驗證細節的基本安全習慣，跟 SPEC 裡「登入帳密錯誤不透露哪個錯」
    是同一種設計精神。
    """
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="請先登入")

    if not authorization or not authorization.startswith("Bearer "):
        raise unauthorized

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise unauthorized

    try:
        payload = decode_access_token(token)
    except Exception as exc:  # PyJWT 對「過期」「簽章不對」「格式錯」會丟出不同子類別例外
        # 注意：這裡刻意用寬鬆的 `except Exception`，因為我們不在乎是哪一種驗證失敗，
        # 統一都當成「請先登入」處理，前面的 docstring 已經解釋為什麼。
        raise unauthorized from exc

    user_id_raw = payload.get("sub")
    try:
        # 教學點——為什麼 int(user_id_raw) 要另外包一層 try/except，不能直接裸寫：
        # token 的簽章驗證只保證「這個 payload 沒被竄改過」，不保證「sub 這個
        # 欄位裡面裝的字串內容就一定能被 int() 解析」。如果 sub 是 None
        # （int(None) 會丟 TypeError）或是像 "not-a-number" 這種非數字字串
        # （int() 會丟 ValueError），這兩種都屬於「這個 token 不能信任」，
        # 理應跟上面 decode 失敗共用同一個 401 分支——而不是讓沒接住的例外
        # 一路往上炸成 500（那樣反而洩漏了「後端處理 token 時發生未預期例外」
        # 這個不該讓使用者知道的內部細節，違反本函式 docstring 的承諾）。
        user_id = int(user_id_raw)
    except (TypeError, ValueError) as exc:
        raise unauthorized from exc

    user = repos.users.get_by_id(user_id)
    if user is None:
        raise unauthorized

    return user
