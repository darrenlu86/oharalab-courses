"""測試 stage6_system/pipeline/update_data.py 與 backfill_actuals.py。

`bootstrap.py` 不在這裡做隔離單元測試——它的 ensure_stage4_models()/
ensure_stage5_text_model() 會對 repo 裡真正的 MODELS_DIR 寫入 joblib
檔案（gitignored 但仍是共用路徑），在 pytest 裡測會對 repo 狀態造成
副作用、也可能跟其他測試/開發流程競爭。這支腳本的正確性已經用手動
E2E 驗證過兩條分支（模型缺失時重訓、模型存在時跳過），紀錄在
stage6_system/report.md，符合 SPEC §7 把「bootstrap＋起站」歸類為
E2E（另由驗證流程執行，不在 pytest 內）的設計。
"""

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.paths import RAW_DIR  # noqa: E402
from stage3_crawler.crawler.db import upsert_daily_weather  # noqa: E402
from stage6_system.pipeline import backfill_actuals, update_data  # noqa: E402


# ---------------------------------------------------------------------------
# update_data.py：--from-csv（離線）
# ---------------------------------------------------------------------------


def test_update_city_from_csv_matches_raw_csv_row_count(fresh_db_conn):
    count = update_data.update_city_from_csv("taipei", fresh_db_conn)
    with (RAW_DIR / "taipei.csv").open(encoding="utf-8") as f:
        expected = sum(1 for _ in f) - 1  # 扣掉 header
    assert count == expected == 4018


def test_update_from_csv_all_cities_matches_db_row_counts(fresh_db_conn):
    counts = update_data.update_from_csv(conn=fresh_db_conn)
    assert counts == {"taipei": 4018, "taichung": 4018, "kaohsiung": 4018}
    total_in_db = fresh_db_conn.execute("SELECT COUNT(*) FROM daily_weather").fetchone()[0]
    assert total_in_db == 4018 * 3


def test_update_city_from_csv_values_match_source_first_row(fresh_db_conn):
    update_data.update_city_from_csv("taipei", fresh_db_conn)
    row = fresh_db_conn.execute(
        "SELECT temp_max, temp_min, wind_dir FROM daily_weather WHERE city='taipei' AND date='2015-01-01'"
    ).fetchone()
    assert row == (13.4, 10.7, 57)  # 對照 data/raw/taipei.csv 第一列的真實數值


# ---------------------------------------------------------------------------
# update_data.py：線上模式（注入假 session，不連網路）
# ---------------------------------------------------------------------------


class _FakeArchiveResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeArchiveSession:
    def __init__(self):
        self.last_params = None
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        self.last_params = params
        start = date.fromisoformat(params["start_date"])
        end = date.fromisoformat(params["end_date"])
        days = (end - start).days + 1
        return _FakeArchiveResponse(
            {
                "daily": {
                    "time": [(start + timedelta(days=i)).isoformat() for i in range(days)],
                    "temperature_2m_max": [20.0 + i for i in range(days)],
                    "temperature_2m_min": [15.0 + i for i in range(days)],
                    "temperature_2m_mean": [17.5 + i for i in range(days)],
                    "precipitation_sum": [1.0] * days,
                    "rain_sum": [1.0] * days,
                    "precipitation_hours": [2.0] * days,
                    "windspeed_10m_max": [10.0] * days,
                    "windgusts_10m_max": [20.0] * days,
                    "winddirection_10m_dominant": [90] * days,
                    "shortwave_radiation_sum": [15.0] * days,
                }
            }
        )


def test_get_last_date_returns_none_when_city_has_no_data(fresh_db_conn):
    assert update_data._get_last_date(fresh_db_conn, "taipei") is None


def test_get_last_date_returns_max_date_after_insert(fresh_db_conn):
    upsert_daily_weather(
        fresh_db_conn,
        {
            "city": "taipei", "date": "2024-05-01", "temp_max": 30.0, "temp_min": 20.0, "temp_mean": 25.0,
            "precipitation_mm": 0.0, "rain_mm": 0.0, "precip_hours": 0.0, "windspeed_max": 5.0,
            "windgusts_max": 10.0, "wind_dir": 90, "radiation": 15.0,
        },
    )
    assert update_data._get_last_date(fresh_db_conn, "taipei") == date(2024, 5, 1)


def test_update_city_from_api_fetches_from_day_after_last_date(fresh_db_conn):
    upsert_daily_weather(
        fresh_db_conn,
        {
            "city": "taipei", "date": "2024-05-01", "temp_max": 30.0, "temp_min": 20.0, "temp_mean": 25.0,
            "precipitation_mm": 0.0, "rain_mm": 0.0, "precip_hours": 0.0, "windspeed_max": 5.0,
            "windgusts_max": 10.0, "wind_dir": 90, "radiation": 15.0,
        },
    )
    session = _FakeArchiveSession()
    today = date(2024, 5, 10)
    count = update_data.update_city_from_api("taipei", fresh_db_conn, session=session, today=today)

    assert session.last_params["start_date"] == "2024-05-02"  # 最新日期隔天
    assert session.last_params["end_date"] == "2024-05-09"  # 昨天（today - 1）
    assert count == 8  # 05-02 ~ 05-09


def test_update_city_from_api_skips_when_already_up_to_date(fresh_db_conn):
    upsert_daily_weather(
        fresh_db_conn,
        {
            "city": "taipei", "date": "2024-05-09", "temp_max": 30.0, "temp_min": 20.0, "temp_mean": 25.0,
            "precipitation_mm": 0.0, "rain_mm": 0.0, "precip_hours": 0.0, "windspeed_max": 5.0,
            "windgusts_max": 10.0, "wind_dir": 90, "radiation": 15.0,
        },
    )
    session = _FakeArchiveSession()
    count = update_data.update_city_from_api("taipei", fresh_db_conn, session=session, today=date(2024, 5, 10))
    assert count == 0
    assert session.calls == 0  # 不需要打 API


def test_update_city_from_api_no_prior_data_defaults_to_last_30_days(fresh_db_conn):
    session = _FakeArchiveSession()
    today = date(2024, 5, 10)
    update_data.update_city_from_api("taipei", fresh_db_conn, session=session, today=today)
    expected_start = (today - timedelta(days=1) - timedelta(days=29)).isoformat()
    assert session.last_params["start_date"] == expected_start


# ---------------------------------------------------------------------------
# backfill_actuals.py
# ---------------------------------------------------------------------------


def _insert_prediction(conn, city, target_date, predicted_label, rain_prob=0.5):
    conn.execute(
        "INSERT INTO predictions (city, target_date, rain_prob, predicted_label, model_version, created_at) "
        "VALUES (?, ?, ?, ?, 'v1', '2024-01-01T00:00:00')",
        (city, target_date, rain_prob, predicted_label),
    )
    conn.commit()


def test_backfill_skips_when_actual_data_not_yet_available(fresh_db_conn):
    _insert_prediction(fresh_db_conn, "taipei", "2024-06-01", predicted_label=1)
    count = backfill_actuals.backfill(fresh_db_conn)
    assert count == 0
    row = fresh_db_conn.execute("SELECT actual_label FROM predictions").fetchone()
    assert row[0] is None


def test_backfill_updates_when_actual_data_exists_and_matches_rain_threshold(fresh_db_conn):
    _insert_prediction(fresh_db_conn, "taipei", "2024-06-01", predicted_label=1)
    upsert_daily_weather(
        fresh_db_conn,
        {
            "city": "taipei", "date": "2024-06-01", "temp_max": 30.0, "temp_min": 20.0, "temp_mean": 25.0,
            "precipitation_mm": 5.0, "rain_mm": 5.0, "precip_hours": 3.0, "windspeed_max": 5.0,
            "windgusts_max": 10.0, "wind_dir": 90, "radiation": 15.0,
        },
    )
    count = backfill_actuals.backfill(fresh_db_conn)
    assert count == 1
    row = fresh_db_conn.execute("SELECT actual_precip_mm, actual_label FROM predictions").fetchone()
    assert row == (5.0, 1)  # 5.0mm >= RAIN_THRESHOLD_MM(1.0) → 下雨


def test_backfill_does_not_reprocess_already_backfilled_rows(fresh_db_conn):
    _insert_prediction(fresh_db_conn, "taipei", "2024-06-01", predicted_label=0)
    upsert_daily_weather(
        fresh_db_conn,
        {
            "city": "taipei", "date": "2024-06-01", "temp_max": 30.0, "temp_min": 20.0, "temp_mean": 25.0,
            "precipitation_mm": 0.0, "rain_mm": 0.0, "precip_hours": 0.0, "windspeed_max": 5.0,
            "windgusts_max": 10.0, "wind_dir": 90, "radiation": 15.0,
        },
    )
    first_count = backfill_actuals.backfill(fresh_db_conn)
    assert first_count == 1

    # 資料庫裡的實際降雨量事後被改掉（模擬資料源修正）；backfill 只處理
    # actual_label IS NULL 的列，已回填過的不應該被第二次呼叫動到。
    fresh_db_conn.execute("UPDATE daily_weather SET precipitation_mm = 99.0 WHERE city='taipei'")
    fresh_db_conn.commit()
    second_count = backfill_actuals.backfill(fresh_db_conn)
    assert second_count == 0
    row = fresh_db_conn.execute("SELECT actual_precip_mm FROM predictions").fetchone()
    assert row[0] == 0.0  # 維持第一次回填的值，沒有被覆寫
