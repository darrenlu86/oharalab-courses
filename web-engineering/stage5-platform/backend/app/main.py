"""
FastAPI 應用程式進入點——建立 app 實例、掛上 CORS、註冊所有路由、（正式模式）掛上前台與後台
兩個前端 build 產物。

跟 stage4 的差異：
1. 多掛了兩支路由模組——`payments`（模擬付款）與 `admin`（後台管理端點，內部已經
   統一掛了 `require_admin` 依賴，見 app/routers/admin.py）。
2. 除了掛前台 `frontend/dist`（沿用 stage4 的 SPA fallback 手法），本階段還多掛了
   一個完全獨立的後台 SPA `admin/dist`，掛載在 `/admin` 這個路徑前綴下——後台是
   「另一個 Vite React app」，不是前台 App 底下的幾個路由，兩邊各自獨立
   build、獨立部署（也可以只部署其中一邊），這是本階段「前台／後台是兩個獨立
   應用」的具體體現，完整理由見 docs/ARCHITECTURE.md。
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings, warn_if_default_secret_key
from app.routers import admin, auth, cart, orders, payments, products
from app.schemas import HealthOut

settings = get_settings()
# 啟動階段的一次性安全檢查——SECRET_KEY 還是預設值時對 stderr 印出警告，
# 完整理由見 app/config.py「SECRET_KEY 沒設定時的安全警告」一節。
warn_if_default_secret_key(settings.secret_key)

app = FastAPI(
    title="BrewGo 沖沖咖啡 API",
    description="沖沖咖啡電商教學範例後端（stage5：完整應用系統·前台＋後台）",
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
app.include_router(payments.router)
app.include_router(admin.router)


@app.get("/api/health", response_model=HealthOut, tags=["health"])
def health_check() -> HealthOut:
    """健康檢查端點——部署後第一個要 curl 的網址，確認服務有正常啟動。"""
    return HealthOut(status="ok")


# 用 __file__ 往上推算 frontend/dist、admin/dist 的絕對路徑，不寫死相對路徑字串——
# 理由跟 stage4 一致：相對路徑會受「執行 uvicorn 時的工作目錄」影響，用 __file__
# 計算出來的絕對路徑，不管從哪個資料夾啟動都一樣正確。
_ROOT_DIR = Path(__file__).resolve().parent.parent.parent
_FRONTEND_DIST = _ROOT_DIR / "frontend" / "dist"
_ADMIN_DIST = _ROOT_DIR / "admin" / "dist"

if _ADMIN_DIST.is_dir():
    # 後台是獨立的 SPA，build 時 vite.config.js 設定了 `base: '/admin/'`（見
    # admin/vite.config.js），所以 dist/index.html 裡引用的資源網址都已經是
    # `/admin/assets/xxx.js` 這種絕對路徑，這裡只要把 assets 掛到對應路徑即可。
    app.mount("/admin/assets", StaticFiles(directory=str(_ADMIN_DIST / "assets")), name="admin-assets")

    @app.get("/admin", include_in_schema=False)
    async def redirect_admin_root() -> RedirectResponse:
        # 瀏覽器打 /admin（沒有結尾斜線）時導去 /admin/，讓下面的 catch-all 路由
        # 能吃到這個請求——這支路由必須寫在 catch-all 之前，且路徑不能跟它重疊。
        return RedirectResponse(url="/admin/")

    @app.get("/admin/{full_path:path}", include_in_schema=False)
    async def serve_admin_spa(full_path: str) -> FileResponse:
        candidate = _ADMIN_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_ADMIN_DIST / "index.html")

if _FRONTEND_DIST.is_dir():
    # 只有前端已經 `npm run build` 過（dist/ 資料夾真的存在）才掛載，開發階段
    # （只跑 `npm run dev`，沒有 build 過）這裡不會生效，也不會報錯——後端這時
    # 只單純提供 API，前端請求都是 Vite 開發伺服器自己處理或透過 proxy 轉過來。
    #
    # 教學點——為什麼不能只掛 `StaticFiles(html=True)` 就結束（meowshop 那樣做就夠了）：
    # meowshop 前端是純多頁 HTML（每個網址對應一個真實檔案），但 stage3 以後的前端是
    # react-router 的 client-side routing——瀏覽器網址列的 `/products/5` 這種路徑
    # 在伺服器端根本沒有對應檔案，`StaticFiles(html=True)` 只會在「整個路徑是資料夾」
    # 時補上 index.html，不會對任意未知路徑做這件事，直接訪問 `/products/5`
    # （重新整理、或分享連結給別人打開）會被伺服器回 404，即使前端 App 本身完全正常。
    # 正確做法（SPA fallback）：先掛 `/assets` 讓 JS/CSS 檔案能被正常抓到，
    # 再用一個「吃掉其他所有路徑」的 catch-all 路由，找不到對應檔案就一律回
    # index.html，剩下的路由交給前端的 react-router 自己接手判斷要顯示哪個頁面
    # （包含判斷是不是真的要顯示 404 頁）。這支 catch-all 一定要放在 `/admin` 那組
    # 路由「之後」註冊：FastAPI 依照路由註冊順序比對，先註冊的先比對到，如果這支
    # `/{full_path:path}`（可以吃掉包含 `/admin/...` 在內的任何路徑）先註冊，
    # 所有 `/admin/*` 的請求都會被它攔截，永遠輪不到後台的 SPA fallback。
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="frontend-assets")
    app.mount("/images", StaticFiles(directory=str(_FRONTEND_DIST / "images")), name="frontend-images")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
