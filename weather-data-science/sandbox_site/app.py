"""教學沙盒網站「福爾摩沙氣象站」的 FastAPI app。

啟動：
    venv/bin/python -m uvicorn sandbox_site.app:app --port 8310

這不是真網站，是 stage3_crawler 的爬蟲練習標的：
- /stations                    關卡一：靜態 HTML 表格解析
- /records?city=&page=         關卡二：翻頁爬蟲（每頁 50 列）
- /api/latest?city=            關卡三：直接打 JSON API
- /comments?city=&page=         合成留言分頁列表
- /announcements, /announcements/{ann_id}   列表→詳情兩層爬取
- /robots.txt                   允許全部，附教學註解

天氣資料（/stations、/records、/api/latest）一律讀 data/raw/*.csv（真實資料）；
留言與公告（/comments、/announcements）一律讀 data/synthetic/*.csv（合成資料）。
沒有 JS，沒有 emoji，回應不故意延遲（爬蟲端的禮貌延遲由 stage3_crawler 自己做）。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.templating import Jinja2Templates

from sandbox_site.data import PAGE_SIZE, CITY_NAME_ZH, KNOWN_CITIES, SandboxData, paginate

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_CSS_PATH = BASE_DIR / "static" / "style.css"

app = FastAPI(title="福爾摩沙氣象站（教學沙盒）")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# 啟動時把四份 CSV 一次讀進記憶體（規模只有幾千列，沒有大到需要延後載入）。
data = SandboxData()

ROBOTS_TXT = """# 福爾摩沙氣象站是教學沙盒網站，全部頁面開放爬蟲練習。
# 這裡刻意保持寬鬆規則，方便學員練習「先讀 robots.txt 再爬」的禮貌習慣；
# 真實網站的 robots.txt 通常會限制更多路徑，不要把這份規則當成一般網站的示範。
User-agent: *
Allow: /
"""


def _validate_city(city: str) -> str:
    if city not in KNOWN_CITIES:
        raise HTTPException(
            status_code=404,
            detail=f"未知城市：{city}（可用：{', '.join(KNOWN_CITIES)}）",
        )
    return city


@app.get("/", response_class=Response)
def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "stations": data.stations,
            "city_names": "、".join(f"{s['name_zh']}({s['city']})" for s in data.stations),
        },
    )


@app.get("/stations", response_class=Response)
def stations(request: Request):
    return templates.TemplateResponse(request, "stations.html", {"stations": data.stations})


@app.get("/records", response_class=Response)
def records(request: Request, city: str = Query("taipei"), page: int = Query(1)):
    city = _validate_city(city)
    all_rows = data.weather_for_city(city)
    rows, total_pages = paginate(all_rows, page)
    return templates.TemplateResponse(
        request,
        "records.html",
        {
            "city": city,
            "city_name_zh": CITY_NAME_ZH[city],
            "rows": rows,
            "columns": list(all_rows[0].keys()) if all_rows else [],
            "page": page,
            "total_pages": total_pages,
        },
    )


@app.get("/api/latest")
def api_latest(city: str = Query("taipei")):
    city = _validate_city(city)
    all_rows = data.weather_for_city(city)
    latest_30 = all_rows[-30:] if len(all_rows) >= 30 else all_rows
    return JSONResponse(content=latest_30)


@app.get("/comments", response_class=Response)
def comments(request: Request, city: str | None = Query(None), page: int = Query(1)):
    if city is not None:
        city = _validate_city(city)
    all_rows = data.comments_for_city(city)
    rows, total_pages = paginate(all_rows, page)
    return templates.TemplateResponse(
        request,
        "comments.html",
        {
            "city": city,
            "city_name_zh": CITY_NAME_ZH.get(city, ""),
            "rows": rows,
            "page": page,
            "total_pages": total_pages,
        },
    )


@app.get("/announcements", response_class=Response)
def announcements_list(request: Request):
    return templates.TemplateResponse(
        request, "announcements_list.html", {"announcements": data.announcements}
    )


@app.get("/announcements/{ann_id}", response_class=Response)
def announcement_detail(request: Request, ann_id: str):
    announcement = data.announcements_by_id.get(ann_id)
    if announcement is None:
        raise HTTPException(status_code=404, detail=f"找不到公告：{ann_id}")
    return templates.TemplateResponse(
        request, "announcement_detail.html", {"announcement": announcement}
    )


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    return PlainTextResponse(content=ROBOTS_TXT, media_type="text/plain")


@app.get("/static/style.css")
def static_style():
    return Response(content=STATIC_CSS_PATH.read_text(encoding="utf-8"), media_type="text/css")
