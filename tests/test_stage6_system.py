"""測試 stage6_system：核心邏輯函式（用 fresh_db_conn 注入的 SQLite 連線）
+ FastAPI 路由（TestClient + `app.dependency_overrides` 換掉真資料庫/模型，
不需要跑過 bootstrap、不依賴 gitignored 的 *.joblib 是否已存在於磁碟）。
"""

import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import matplotlib

matplotlib.use("Agg")

from fastapi.testclient import TestClient  # noqa: E402

from stage3_crawler.crawler.db import upsert_comment, upsert_daily_weather  # noqa: E402
from stage4_ml_structured.features import FEATURE_COLUMNS  # noqa: E402
from stage6_system import app as stage6_app  # noqa: E402


# ---------------------------------------------------------------------------
# 假模型：不依賴真的 joblib（那些檔案 gitignored，全新 clone 未必存在），
# 只驗證 app 的邏輯有沒有正確呼叫 predict/predict_proba 介面。
# ---------------------------------------------------------------------------


class _FakeRainModel:
    def predict_proba(self, X):
        return np.array([[0.3, 0.7]] * len(X))


class _FakeTempModel:
    def predict(self, X):
        return np.array([28.5] * len(X))


class _FakeVectorizer:
    def transform(self, tokens):
        return list(tokens)


class _FakeTextModel:
    """交替回傳正面/負面，機率固定，方便斷言總數與比例。"""

    def predict_proba(self, X):
        return np.array([[0.4, 0.6] if i % 2 == 0 else [0.7, 0.3] for i in range(len(X))])


def _fake_models() -> dict:
    return {
        "rain": _FakeRainModel(),
        "temp": _FakeTempModel(),
        "vectorizer": _FakeVectorizer(),
        "text_mlp": _FakeTextModel(),
    }


def _insert_daily_weather_days(conn, city: str, n_days: int, start: date) -> None:
    """插入連續 n_days 天的天氣資料（數值用簡單公式生成，不追求真實分布，
    只為了讓 build_features() 的 rolling_30 有足夠資料可以算)。
    """
    for i in range(n_days):
        d = start + timedelta(days=i)
        upsert_daily_weather(
            conn,
            {
                "city": city,
                "date": d.isoformat(),
                "temp_max": 25.0 + (i % 5),
                "temp_min": 18.0 + (i % 3),
                "temp_mean": 21.0,
                "precipitation_mm": float(i % 10),
                "rain_mm": float(i % 10),
                "precip_hours": 1.0,
                "windspeed_max": 10.0,
                "windgusts_max": 20.0,
                "wind_dir": 90,
                "radiation": 15.0,
            },
        )


@pytest.fixture
def db_conn(fresh_db):
    # 注意：不能直接沿用 conftest.py 的 fresh_db_conn——那個連線是在 pytest
    # 測試函式的主執行緒建立的，但 FastAPI TestClient 對 sync def 路由是丟
    # 進另一個 worker thread 執行（真的測過才發現：直接複用 fresh_db_conn
    # 會在 TestClient 呼叫時炸出
    # `SQLite objects created in a thread can only be used in that same
    # thread`）。這裡改用 `check_same_thread=False` 自己開一條連線——測試
    # 全程只有一個請求在跑（不會真的並發），跨執行緒依序使用是安全的。
    conn = sqlite3.connect(fresh_db, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# load_daily_weather_df / fetch_overview_data
# ---------------------------------------------------------------------------


def test_load_daily_weather_df_renames_columns_to_api_names(db_conn):
    _insert_daily_weather_days(db_conn, "taipei", 35, date(2024, 1, 1))
    df = stage6_app.load_daily_weather_df(db_conn)
    assert "temperature_2m_max" in df.columns
    assert "precipitation_sum" in df.columns
    assert "temp_max" not in df.columns  # 舊的 DB 欄名不應該留著
    assert len(df) == 35
    assert "month" in df.columns and "year" in df.columns


def test_fetch_overview_data_returns_ascending_order_and_respects_limit(db_conn):
    _insert_daily_weather_days(db_conn, "taipei", 40, date(2024, 1, 1))
    result = stage6_app.fetch_overview_data(db_conn, days=30)
    assert len(result["taipei"]) == 30
    dates = [r["date"] for r in result["taipei"]]
    assert dates == sorted(dates)  # 升序（給折線圖從左到右畫）
    assert result["taichung"] == []  # 沒插資料的城市回傳空列表，不是報錯


# ---------------------------------------------------------------------------
# compute_predictions
# ---------------------------------------------------------------------------


def test_compute_predictions_writes_one_row_per_city_and_is_idempotent(db_conn):
    for city in stage6_app.CITIES:
        _insert_daily_weather_days(db_conn, city, 35, date(2024, 1, 1))
    models = _fake_models()

    results = stage6_app.compute_predictions(db_conn, models)
    assert len(results) == len(stage6_app.CITIES)
    for r in results:
        assert set(r.keys()) == {"city", "base_date", "target_date", "rain_prob", "predicted_label", "temp_pred"}
        assert r["rain_prob"] == pytest.approx(0.7)
        assert r["predicted_label"] == 1
        assert r["temp_pred"] == pytest.approx(28.5)

    count_after_first = db_conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    assert count_after_first == len(stage6_app.CITIES)

    # 重跑一次：同 city/target_date/model_version 應該覆寫，不是新增列。
    stage6_app.compute_predictions(db_conn, models)
    count_after_second = db_conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    assert count_after_second == count_after_first


def test_compute_predictions_skips_city_with_insufficient_history(db_conn):
    # 只插 10 天（< rolling_30 需要的 30 天），build_features 會把這個城市
    # 的所有列都丟掉，compute_predictions 應該優雅跳過，不是報錯。
    _insert_daily_weather_days(db_conn, "taipei", 10, date(2024, 1, 1))
    results = stage6_app.compute_predictions(db_conn, _fake_models())
    assert results == []


def test_fetch_latest_predictions_returns_one_row_per_city(db_conn):
    for city in stage6_app.CITIES:
        _insert_daily_weather_days(db_conn, city, 35, date(2024, 1, 1))
    stage6_app.compute_predictions(db_conn, _fake_models())
    latest = stage6_app.fetch_latest_predictions(db_conn)
    assert len(latest) == len(stage6_app.CITIES)
    assert {r["city"] for r in latest} == set(stage6_app.CITIES)


# ---------------------------------------------------------------------------
# compute_sentiment_summary
# ---------------------------------------------------------------------------


def test_compute_sentiment_summary_empty_comments_returns_zero(db_conn):
    summary = stage6_app.compute_sentiment_summary(db_conn, _fake_models())
    assert summary == {"total": 0, "positive": 0, "negative": 0, "latest": []}


def test_compute_sentiment_summary_counts_match_fake_model_pattern(db_conn):
    for i in range(6):
        upsert_comment(db_conn, f"c{i}", "taipei", "2024-01-01", 5, f"測試留言{i}", "2024-01-01T00:00:00")
    summary = stage6_app.compute_sentiment_summary(db_conn, _fake_models())
    assert summary["total"] == 6
    # _FakeTextModel 偶數 index 給 0.6（正面），奇數給 0.3（負面）—— 6 筆應該 3 正 3 負。
    assert summary["positive"] == 3
    assert summary["negative"] == 3
    assert len(summary["latest"]) == 6


# ---------------------------------------------------------------------------
# compute_monitoring_summary
# ---------------------------------------------------------------------------


def test_compute_monitoring_summary_empty(db_conn):
    summary = stage6_app.compute_monitoring_summary(db_conn)
    assert summary == {"records": [], "total": 0, "backfilled_count": 0, "accuracy": None, "trend": []}


def test_compute_monitoring_summary_computes_accuracy_and_trend(db_conn):
    db_conn.execute(
        "INSERT INTO predictions (city, target_date, rain_prob, predicted_label, actual_precip_mm, actual_label, "
        "model_version, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("taipei", "2024-02-01", 0.7, 1, 5.0, 1, "v1", "2024-01-31T00:00:00"),
    )
    db_conn.execute(
        "INSERT INTO predictions (city, target_date, rain_prob, predicted_label, actual_precip_mm, actual_label, "
        "model_version, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("taichung", "2024-02-02", 0.2, 0, 5.0, 1, "v1", "2024-02-01T00:00:00"),  # 預測錯誤
    )
    db_conn.execute(
        "INSERT INTO predictions (city, target_date, rain_prob, predicted_label, model_version, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("kaohsiung", "2024-02-03", 0.5, 1, "v1", "2024-02-02T00:00:00"),  # 尚未回填
    )
    db_conn.commit()

    summary = stage6_app.compute_monitoring_summary(db_conn)
    assert summary["total"] == 3
    assert summary["backfilled_count"] == 2
    assert summary["accuracy"] == pytest.approx(0.5)  # 2 筆回填，1 對 1 錯
    assert len(summary["trend"]) == 2


# ---------------------------------------------------------------------------
# FastAPI 路由（TestClient + dependency_overrides）
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_conn):
    def override_get_db():
        yield db_conn

    stage6_app.app.dependency_overrides[stage6_app.get_db] = override_get_db
    stage6_app.app.dependency_overrides[stage6_app.get_models_or_503] = _fake_models
    yield TestClient(stage6_app.app)
    stage6_app.app.dependency_overrides.clear()


def test_overview_page_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "總覽" in resp.text


def test_api_overview_returns_json_with_all_cities(client):
    resp = client.get("/api/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == set(stage6_app.CITIES)


def test_predict_get_page_returns_200_with_no_predictions_yet(client):
    resp = client.get("/predict")
    assert resp.status_code == 200
    assert "尚無預測紀錄" in resp.text


def test_predict_post_triggers_computation_and_shows_results(client, db_conn):
    for city in stage6_app.CITIES:
        _insert_daily_weather_days(db_conn, city, 35, date(2024, 1, 1))
    resp = client.post("/predict")
    assert resp.status_code == 200
    assert "已重新預測" in resp.text
    count = db_conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    assert count == len(stage6_app.CITIES)


def test_api_predict_post_returns_json_list(client, db_conn):
    for city in stage6_app.CITIES:
        _insert_daily_weather_days(db_conn, city, 35, date(2024, 1, 1))
    resp = client.post("/api/predict")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == len(stage6_app.CITIES)


def test_sentiment_page_returns_200(client):
    resp = client.get("/sentiment")
    assert resp.status_code == 200
    assert "留言情感面板" in resp.text


def test_monitoring_page_returns_200(client):
    resp = client.get("/monitoring")
    assert resp.status_code == 200
    assert "模型監測" in resp.text


def test_models_missing_returns_503_not_500(db_conn):
    def override_get_db():
        yield db_conn

    def override_models_missing():
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="模型缺失，請先執行 bootstrap")

    stage6_app.app.dependency_overrides[stage6_app.get_db] = override_get_db
    stage6_app.app.dependency_overrides[stage6_app.get_models_or_503] = override_models_missing
    client = TestClient(stage6_app.app, raise_server_exceptions=False)
    resp = client.get("/sentiment")
    stage6_app.app.dependency_overrides.clear()
    assert resp.status_code == 503


def test_static_chartjs_and_style_are_served(client):
    resp_js = client.get("/static/vendor/chart.umd.min.js")
    assert resp_js.status_code == 200
    assert len(resp_js.text) > 10_000  # 真的 vendored 進來的檔案，不是空殼

    resp_css = client.get("/static/style.css")
    assert resp_css.status_code == 200
