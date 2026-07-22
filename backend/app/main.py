"""
FastAPI 應用程式進入點——建立 app 實例、掛上 CORS、註冊所有路由、掛上前端靜態檔。

在架構中的位置：整個後端的「組裝點」，把 routers/ 底下各自獨立的路由模組
串成一個完整的 app；本身不寫任何商業邏輯。

為什麼要同時 serve 前端靜態檔（`StaticFiles` 掛在 "/"）：
本專案前端是純 HTML/CSS/JS、沒有 build step，讓同一個 FastAPI process 直接把
`frontend/` 資料夾當成靜態網站服務，學員只要跑一個指令（uvicorn）就同時有了
「網站」跟「API」，不用另外開一個前端 server、也完全不會遇到跨網域（CORS）問題
（因為前後端根本是同一個來源）。即使如此，我們還是加了 CORSMiddleware——
是為了「以後想把前後端拆開部署」預留彈性（例如前端丟到 CDN、後端獨立部署），
這種情況下就需要靠 CORS 設定允許前端網域呼叫後端 API。
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routers import auth, cart, orders, payments, products
from app.schemas import HealthOut

settings = get_settings()

app = FastAPI(
    title="MeowShop 喵喵商店 API",
    description="貓咪主題電商教學範例後端",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # 教學點——為什麼 allow_credentials 要是 False，不能跟萬用字元一起開：
    # 瀏覽器 CORS 規範刻意設計成「allow_origins=* 與 allow_credentials=True
    # 不可以同時開」——如果兩者同開，Starlette 實際上不會回傳字面上的 "*"，
    # 而是把請求帶來的 Origin 原樣回填進 Access-Control-Allow-Origin，等於
    # 「任何網站都能發出帶憑證的跨網域請求並讀到回應」，這正是瀏覽器要防止的
    # CSRF/憑證外流風險。本專案的登入態是 JWT 存在 localStorage、由前端 JS
    # 手動加進 Authorization header（不是瀏覽器自動夾帶的 cookie），所以本來
    # 就不需要 allow_credentials=True；把它關掉可以完全避開這個組合風險。
    # 注意：如果以後真的要改成 cookie-based session（例如「記住我」功能），
    # 才需要重新打開 allow_credentials，但那時 CORS_ORIGINS 就不能再用 "*"，
    # 必須明確列出允許的網域清單。
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(payments.router)


@app.get("/api/health", response_model=HealthOut, tags=["health"])
def health_check() -> HealthOut:
    """健康檢查端點——部署後第一個要 curl 的網址，確認服務跟資料庫後端設定正常。"""
    current_settings = get_settings()
    return HealthOut(status="ok", db_backend=current_settings.db_backend)


# 注意：這裡刻意用 `__file__` 往上推算 frontend/ 的絕對路徑，而不是直接寫死
# `StaticFiles(directory="../frontend")` 這種相對路徑字串。相對路徑是「相對於
# 目前執行指令時的工作目錄」，如果哪天有人在專案根目錄（而不是 backend/ 目錄）
# 下執行 uvicorn，相對路徑就會指到錯誤的地方甚至整個 app 啟動失敗；
# 用 __file__ 計算出來的路徑，不管從哪個工作目錄啟動都一樣正確。
_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
