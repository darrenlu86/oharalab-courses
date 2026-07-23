"""天氣智慧儀表板（stage6_system，AI-12）的 FastAPI app。

啟動（先跑過 bootstrap 確保資料庫與模型都在）：
    venv/bin/python -m stage6_system.pipeline.bootstrap
    venv/bin/python -m uvicorn stage6_system.app:app --port 8320

四個功能頁：
    /            總覽：三城市近 30 天溫度/降雨圖
    /predict     明日降雨預測（POST 觸發重新預測，寫入 predictions 表）
    /sentiment   留言情感面板（對 comments 表跑 stage5 模型）
    /monitoring  模型監測：歷史預測 vs 回填實際

每頁都有對應的 `/api/...` JSON 端點，路由邏輯全部拆成獨立函式
（`fetch_*`/`compute_*`），FastAPI route 本身只負責讀 Depends 注入的
db/models 再呼叫這些函式——這讓 `tests/test_stage6_system.py` 可以用
`app.dependency_overrides` 換成測試用的假資料庫與假模型，不需要真的跑過
bootstrap 或連接正式資料庫。
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.templating import Jinja2Templates

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.paths import DB_PATH  # noqa: E402
from stage4_ml_structured.features import FEATURE_COLUMNS, RAIN_THRESHOLD_MM, build_features  # noqa: E402
from stage4_ml_structured.train import MODEL_VERSION as STAGE4_MODEL_VERSION  # noqa: E402
from stage4_ml_structured.train import MODELS_DIR as STAGE4_MODELS_DIR  # noqa: E402
from stage5_ml_unstructured.text_features import tokenize  # noqa: E402
from stage5_ml_unstructured.train_text import MODEL_VERSION as STAGE5_MODEL_VERSION  # noqa: E402
from stage5_ml_unstructured.train_text import MODELS_DIR as STAGE5_MODELS_DIR  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="天氣智慧儀表板（教學系統）")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

CITIES = ["taipei", "taichung", "kaohsiung"]
CITY_NAME_ZH = {"taipei": "台北", "taichung": "台中", "kaohsiung": "高雄"}

OVERVIEW_DAYS = 30
SENTIMENT_LATEST_N = 20


# ---------------------------------------------------------------------------
# 依賴注入：資料庫連線、模型（測試用 app.dependency_overrides 換掉這兩個）
# ---------------------------------------------------------------------------


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_models() -> dict:
    """載入 stage4（降雨/高溫）與 stage5（文字情感）模型。

    找不到檔案時丟 FileNotFoundError，路由層接住轉成 HTTP 503，提示先跑
    bootstrap——這不是「壞掉」，是「還沒初始化」，兩者訊息要分清楚。
    """
    paths = {
        "rain": STAGE4_MODELS_DIR / f"rain_random_forest_{STAGE4_MODEL_VERSION}.joblib",
        "temp": STAGE4_MODELS_DIR / f"temp_random_forest_{STAGE4_MODEL_VERSION}.joblib",
        "vectorizer": STAGE5_MODELS_DIR / f"text_vectorizer_{STAGE5_MODEL_VERSION}.joblib",
        "text_mlp": STAGE5_MODELS_DIR / f"text_mlp_{STAGE5_MODEL_VERSION}.joblib",
    }
    missing = [name for name, p in paths.items() if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"缺少模型檔案 {missing}，請先執行："
            "venv/bin/python -m stage6_system.pipeline.bootstrap"
        )
    return {name: joblib.load(p) for name, p in paths.items()}


# ---------------------------------------------------------------------------
# 核心邏輯（純函式，吃 conn/models，不碰 Request/Response，方便單元測試）
# ---------------------------------------------------------------------------


def load_daily_weather_df(conn: sqlite3.Connection) -> pd.DataFrame:
    """把 `daily_weather` 表讀成 `stage4_ml_structured.features.build_features()`
    看得懂的欄名（API 命名，不是 DB 命名）。

    **這裡曾經真的漏掉這一步**：第一版 `compute_predictions()` 直接呼叫
    `build_features()`（預設吃 `stage2_eda.weather_eda.load_all_cities()`,
    也就是 `data/raw/*.csv`），完全沒有讀資料庫——結果是不管
    `pipeline/update_data.py` 幫資料庫補了多少新資料,`/predict` 的預測
    基準日永遠停在 CSV 最後一天（2025-12-31），資料流水線形同虛設。
    手動測試「先 update_data.py 補到昨天，再重新預測」這個流程時才發現
    預測基準日沒有變,才抓到這個問題。修正方式：預測邏輯改吃資料庫內容
    （這支函式），CSV 只在 stage2/stage4 的訓練與分析情境下使用。
    """
    rows = conn.execute(
        "SELECT city, date, temp_max, temp_min, temp_mean, precipitation_mm, rain_mm, "
        "precip_hours, windspeed_max, windgusts_max, wind_dir, radiation FROM daily_weather"
    ).fetchall()
    df = pd.DataFrame([dict(r) for r in rows])
    df = df.rename(
        columns={
            "temp_max": "temperature_2m_max",
            "temp_min": "temperature_2m_min",
            "temp_mean": "temperature_2m_mean",
            "precipitation_mm": "precipitation_sum",
            "rain_mm": "rain_sum",
            "precip_hours": "precipitation_hours",
            "windspeed_max": "windspeed_10m_max",
            "windgusts_max": "windgusts_10m_max",
            "wind_dir": "winddirection_10m_dominant",
            "radiation": "shortwave_radiation_sum",
        }
    )
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    return df


def fetch_overview_data(conn: sqlite3.Connection, days: int = OVERVIEW_DAYS) -> dict[str, list[dict]]:
    result = {}
    for city in CITIES:
        rows = conn.execute(
            "SELECT date, temp_max, temp_min, precipitation_mm FROM daily_weather "
            "WHERE city = ? ORDER BY date DESC LIMIT ?",
            (city, days),
        ).fetchall()
        result[city] = [dict(r) for r in reversed(rows)]
    return result


def compute_predictions(conn: sqlite3.Connection, models: dict) -> list[dict]:
    """用最新一天的特徵預測「明天」的降雨機率，寫入 predictions 表
    （同 city/target_date/model_version 已存在就覆寫，冪等）。
    """
    df = build_features(df=load_daily_weather_df(conn), require_target=False)
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    results = []
    for city in CITIES:
        city_df = df[df["city"] == city].sort_values("date")
        if city_df.empty:
            continue
        latest = city_df.iloc[-1]
        X = latest[FEATURE_COLUMNS].to_frame().T.astype(float)
        rain_prob = float(models["rain"].predict_proba(X)[0, 1])
        predicted_label = int(rain_prob >= 0.5)
        temp_pred = float(models["temp"].predict(X)[0])
        base_date = latest["date"]
        target_date = (base_date + pd.Timedelta(days=1)).date().isoformat()

        conn.execute(
            """
            INSERT INTO predictions (city, target_date, rain_prob, predicted_label, model_version, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(city, target_date, model_version) DO UPDATE SET
                rain_prob=excluded.rain_prob, predicted_label=excluded.predicted_label,
                created_at=excluded.created_at
            """,
            (city, target_date, rain_prob, predicted_label, STAGE4_MODEL_VERSION, created_at),
        )
        results.append(
            {
                "city": city,
                "base_date": base_date.date().isoformat(),
                "target_date": target_date,
                "rain_prob": rain_prob,
                "predicted_label": predicted_label,
                "temp_pred": temp_pred,
            }
        )
    conn.commit()
    return results


def fetch_latest_predictions(conn: sqlite3.Connection) -> list[dict]:
    """每個城市最新一筆預測（不管有沒有回填），給 /predict 頁面顯示用。"""
    rows = conn.execute(
        """
        SELECT p.city, p.target_date, p.rain_prob, p.predicted_label, p.actual_label, p.created_at
        FROM predictions p
        INNER JOIN (
            SELECT city, MAX(created_at) AS max_created_at FROM predictions GROUP BY city
        ) latest ON p.city = latest.city AND p.created_at = latest.max_created_at
        """
    ).fetchall()
    return [dict(r) for r in rows]


def compute_sentiment_summary(conn: sqlite3.Connection, models: dict, limit_latest: int = SENTIMENT_LATEST_N) -> dict:
    rows = conn.execute("SELECT comment_key, city, date, rating, content FROM comments").fetchall()
    if not rows:
        return {"total": 0, "positive": 0, "negative": 0, "latest": []}

    df = pd.DataFrame([dict(r) for r in rows])
    tokens = df["content"].apply(tokenize)
    X = models["vectorizer"].transform(tokens)
    proba = models["text_mlp"].predict_proba(X)[:, 1]
    df["predicted_label"] = (proba >= 0.5).astype(int)
    df["predicted_proba"] = proba

    latest = df.sort_values("date", ascending=False).head(limit_latest)
    return {
        "total": len(df),
        "positive": int((df["predicted_label"] == 1).sum()),
        "negative": int((df["predicted_label"] == 0).sum()),
        "latest": latest[
            ["comment_key", "city", "date", "rating", "content", "predicted_label", "predicted_proba"]
        ].to_dict("records"),
    }


def compute_monitoring_summary(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        "SELECT city, target_date, rain_prob, predicted_label, actual_precip_mm, actual_label, "
        "model_version, created_at FROM predictions ORDER BY target_date"
    ).fetchall()
    records = [dict(r) for r in rows]
    backfilled = [r for r in records if r["actual_label"] is not None]

    accuracy = None
    trend = []
    if backfilled:
        correct_so_far = 0
        for i, r in enumerate(backfilled, start=1):
            if r["predicted_label"] == r["actual_label"]:
                correct_so_far += 1
            trend.append({"target_date": r["target_date"], "cumulative_accuracy": correct_so_far / i})
        accuracy = trend[-1]["cumulative_accuracy"]

    return {
        "records": records,
        "total": len(records),
        "backfilled_count": len(backfilled),
        "accuracy": accuracy,
        "trend": trend,
    }


def get_models_or_503() -> dict:
    """`get_models()` 的 HTTP 包裝：找不到模型檔案時回 503 + 說明，而不是
    未捕捉例外的 500 堆疊。所有需要模型的路由都用 `Depends(get_models_or_503)`
    注入，測試時用 `app.dependency_overrides[get_models_or_503]` 換成假模型。
    """
    try:
        return get_models()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


# ---------------------------------------------------------------------------
# 頁面路由
# ---------------------------------------------------------------------------


@app.get("/", response_class=Response)
def overview_page(request: Request, conn=Depends(get_db)):
    data = fetch_overview_data(conn)
    return templates.TemplateResponse(
        request,
        "overview.html",
        {"data_json": json.dumps(data), "city_names": CITY_NAME_ZH},
    )


@app.get("/api/overview")
def api_overview(conn=Depends(get_db)):
    return JSONResponse(content=fetch_overview_data(conn))


@app.get("/predict", response_class=Response)
def predict_page(request: Request, conn=Depends(get_db)):
    predictions = fetch_latest_predictions(conn)
    return templates.TemplateResponse(
        request,
        "predict.html",
        {"predictions": predictions, "city_names": CITY_NAME_ZH, "rain_threshold": RAIN_THRESHOLD_MM},
    )


@app.post("/predict", response_class=Response)
def predict_trigger(request: Request, conn=Depends(get_db), models=Depends(get_models_or_503)):
    compute_predictions(conn, models)
    predictions = fetch_latest_predictions(conn)
    return templates.TemplateResponse(
        request,
        "predict.html",
        {"predictions": predictions, "city_names": CITY_NAME_ZH, "rain_threshold": RAIN_THRESHOLD_MM, "just_predicted": True},
    )


@app.post("/api/predict")
def api_predict(conn=Depends(get_db), models=Depends(get_models_or_503)):
    return JSONResponse(content=compute_predictions(conn, models))


@app.get("/sentiment", response_class=Response)
def sentiment_page(request: Request, conn=Depends(get_db), models=Depends(get_models_or_503)):
    summary = compute_sentiment_summary(conn, models)
    return templates.TemplateResponse(
        request,
        "sentiment.html",
        {"summary": summary, "city_names": CITY_NAME_ZH},
    )


@app.get("/api/sentiment")
def api_sentiment(conn=Depends(get_db), models=Depends(get_models_or_503)):
    return JSONResponse(content=compute_sentiment_summary(conn, models))


@app.get("/monitoring", response_class=Response)
def monitoring_page(request: Request, conn=Depends(get_db)):
    summary = compute_monitoring_summary(conn)
    return templates.TemplateResponse(
        request,
        "monitoring.html",
        {"summary": summary, "city_names": CITY_NAME_ZH},
    )


@app.get("/api/monitoring")
def api_monitoring(conn=Depends(get_db)):
    return JSONResponse(content=compute_monitoring_summary(conn))


@app.get("/static/vendor/chart.umd.min.js")
def static_chartjs():
    return Response(
        content=(STATIC_DIR / "vendor" / "chart.umd.min.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
    )


@app.get("/static/style.css")
def static_style():
    return Response(content=(STATIC_DIR / "style.css").read_text(encoding="utf-8"), media_type="text/css")
