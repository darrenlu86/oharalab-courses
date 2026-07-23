"""
FastAPI 應用程式進入點——建立 app 實例、掛上 CORS、註冊所有路由、（正式模式）掛上前端 build 產物。

跟 stage3（純前端）最大的不同：這裡多了一整個後端 process。跟 meowshop 的
main.py 是同一套「同時 serve 前端靜態檔」設計，理由也相同：前後端同一個 process
就不會遇到跨網域（CORS）問題、學員也只需要記得啟動一個服務。

**但本階段開發時預設走「開發分離模式」**：前端用 `npm run dev`（Vite 開發伺服器，
埠號 5173）搭配 vite.config.js 的 proxy 設定把 `/api` 轉給這支後端（埠號 8004），
後端這裡的 StaticFiles 掛載只有在 `frontend/dist/` 真的存在時才會生效
（也就是先跑過 `npm run build`）——這是刻意設計成「兩種模式都支援，靠有沒有
build 產物自動判斷」，兩種模式的教學意義寫在 docs/DEPLOY.md「開發環境代理 vs
正式合體 serve」一節。
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings, warn_if_default_secret_key
from app.routers import auth, cart, orders, products
from app.schemas import HealthOut

settings = get_settings()
# 啟動階段的一次性安全檢查——SECRET_KEY 還是預設值時對 stderr 印出警告，
# 完整理由見 app/config.py「SECRET_KEY 沒設定時的安全警告」一節。
warn_if_default_secret_key(settings.secret_key)

app = FastAPI(
    title="BrewGo 沖沖咖啡 API",
    description="沖沖咖啡電商教學範例後端（stage4：互動式動態網頁·後端）",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # allow_credentials 刻意設 False：本專案登入態是 JWT 存在瀏覽器（localStorage），
    # 由前端 JS 手動加進 Authorization header，不是瀏覽器自動夾帶的 cookie，
    # 本來就不需要 allow_credentials=True；跟 CORS_ORIGINS="*" 同時開會有安全疑慮
    # （瀏覽器規範禁止兩者同開，實際行為會退化成把任何來源都原樣允許），
    # 完整理由見 docs/ARCHITECTURE.md「CORS 設定」一節。
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(cart.router)
app.include_router(orders.router)


@app.get("/api/health", response_model=HealthOut, tags=["health"])
def health_check() -> HealthOut:
    """健康檢查端點——部署後第一個要 curl 的網址，確認服務有正常啟動。"""
    return HealthOut(status="ok")


# 用 __file__ 往上推算 frontend/dist 的絕對路徑，不寫死相對路徑字串——理由跟
# meowshop 的 main.py 一致：相對路徑會受「執行 uvicorn 時的工作目錄」影響，
# 用 __file__ 計算出來的絕對路徑，不管從哪個資料夾啟動都一樣正確。
_FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.is_dir():
    # 只有前端已經 `npm run build` 過（dist/ 資料夾真的存在）才掛載，開發階段
    # （只跑 `npm run dev`，沒有 build 過）這裡不會生效，也不會報錯——後端這時
    # 只單純提供 API，前端請求都是 Vite 開發伺服器自己處理或透過 proxy 轉過來。
    #
    # 教學點——為什麼不能只掛 `StaticFiles(html=True)` 就結束（meowshop 那樣做就夠了）：
    # meowshop 前端是純多頁 HTML（每個網址對應一個真實檔案），但 stage3/4 前端是
    # react-router 的 client-side routing——瀏覽器網址列的 `/products/5` 這種路徑
    # 在伺服器端根本沒有對應檔案，`StaticFiles(html=True)` 只會在「整個路徑是資料夾」
    # 時補上 index.html，不會對任意未知路徑做這件事，直接訪問 `/products/5`
    # （重新整理、或分享連結給別人打開）會被伺服器回 404，即使前端 App 本身完全正常。
    # 正確做法（SPA fallback）：先掛 `/assets` 讓 JS/CSS 檔案能被正常抓到，
    # 再用一個「吃掉其他所有路徑」的 catch-all 路由，找不到對應檔案就一律回
    # index.html，剩下的路由交給前端的 react-router 自己接手判斷要顯示哪個頁面
    # （包含判斷是不是真的要顯示 404 頁）。
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="frontend-assets")
    app.mount("/images", StaticFiles(directory=str(_FRONTEND_DIST / "images")), name="frontend-images")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
