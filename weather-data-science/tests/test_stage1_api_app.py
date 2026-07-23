"""測試 stage1_api_app：mock AI 服務（規則式回覆）與天氣速報 CLI。

網路呼叫（forecast API、mock AI 服務）在測試裡全部用注入的假 session/
TestClient 取代，不連真實網路，符合 SPEC §7。
"""

import json
import sys
from pathlib import Path

import pytest
import requests
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stage1_api_app import weather_brief  # noqa: E402
from stage1_api_app.mock_ai_server import DEFAULT_API_KEY, app as mock_app, generate_advice  # noqa: E402

mock_client = TestClient(mock_app)


# ---------------------------------------------------------------------------
# weather_code_desc / build_ai_prompt / build_briefing_text
# ---------------------------------------------------------------------------


def test_weather_code_desc_known_code():
    assert weather_brief.weather_code_desc(95) == "雷雨"
    assert weather_brief.weather_code_desc(0) == "晴朗"


def test_weather_code_desc_unknown_code_does_not_crash():
    result = weather_brief.weather_code_desc(12345)
    assert "未知代碼" in result


SAMPLE_FORECAST = {
    "daily": {
        "time": ["2026-07-24", "2026-07-25"],
        "weathercode": [95, 51],
        "temperature_2m_max": [34.1, 31.3],
        "temperature_2m_min": [25.2, 26.3],
        "precipitation_probability_max": [29, 49],
        "precipitation_sum": [1.8, 0.6],
        "windspeed_10m_max": [20.9, 25.8],
    }
}


def test_build_ai_prompt_matches_mock_server_regex():
    prompt = weather_brief.build_ai_prompt("台北", SAMPLE_FORECAST)
    from stage1_api_app.mock_ai_server import TODAY_PATTERN, TOMORROW_PATTERN

    today_match = TODAY_PATTERN.search(prompt)
    tomorrow_match = TOMORROW_PATTERN.search(prompt)
    assert today_match is not None, f"今天欄位格式與 mock server 正規表示式對不上：{prompt!r}"
    assert tomorrow_match is not None
    assert today_match.groups() == ("34.1", "25.2", "29", "20.9")


def test_build_briefing_text_contains_key_fields():
    text = weather_brief.build_briefing_text("台北", SAMPLE_FORECAST, "測試建議文字", "測試來源")
    assert "台北" in text
    assert "34.1" in text
    assert "測試建議文字" in text
    assert "測試來源" in text


# ---------------------------------------------------------------------------
# get_forecast --offline（讀真實 bundled 樣本）
# ---------------------------------------------------------------------------


def test_load_offline_forecast_returns_real_bundled_sample():
    forecast = weather_brief.load_offline_forecast("taipei")
    assert "daily" in forecast
    assert len(forecast["daily"]["time"]) == 2
    # 樣本檔案本身有 latitude/longitude 欄位，是 Open-Meteo API 原始回應的一部分。
    assert "latitude" in forecast
    assert "longitude" in forecast


def test_get_forecast_offline_true_does_not_need_session():
    forecast = weather_brief.get_forecast("taichung", offline=True)
    assert forecast["daily"]["time"][0]  # 有資料即可，不 assert 具體日期（樣本會隨時間過期）


def test_get_forecast_unknown_offline_city_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        weather_brief.load_offline_forecast("nowhere")


# ---------------------------------------------------------------------------
# fetch_forecast：注入假 session，測重試與最終失敗
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FlakySession:
    """前兩次呼叫丟例外，第三次成功——驗證 fetch_forecast 的重試邏輯。"""

    def __init__(self, fail_times: int, payload=None):
        self.fail_times = fail_times
        self.calls = 0
        self.payload = payload or SAMPLE_FORECAST

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise requests.exceptions.Timeout("模擬逾時")
        return _FakeResponse(self.payload)


class _AlwaysFailSession:
    def __init__(self):
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        raise requests.exceptions.ConnectionError("模擬連線失敗")


def test_fetch_forecast_retries_then_succeeds():
    session = _FlakySession(fail_times=2)
    forecast = weather_brief.fetch_forecast("taipei", session=session)
    assert forecast == SAMPLE_FORECAST
    assert session.calls == 3  # 前兩次失敗 + 第三次成功，證明真的有重試


def test_fetch_forecast_gives_up_after_max_retries():
    session = _AlwaysFailSession()
    with pytest.raises(RuntimeError):
        weather_brief.fetch_forecast("taipei", session=session)
    # MAX_RETRIES=2 代表最多嘗試 3 次（1 次首試 + 2 次重試）
    assert session.calls == weather_brief.MAX_RETRIES + 1


# ---------------------------------------------------------------------------
# mock_ai_server：規則式回覆 + Chat Completions 相容格式
# ---------------------------------------------------------------------------


def test_generate_advice_high_rain_probability():
    prompt = weather_brief.build_ai_prompt(
        "高雄",
        {
            "daily": {
                "time": ["2026-01-01", "2026-01-02"],
                "weathercode": [95, 95],
                "temperature_2m_max": [30.0, 28.0],
                "temperature_2m_min": [27.0, 24.0],
                "precipitation_probability_max": [80, 70],
                "precipitation_sum": [20.0, 15.0],
                "windspeed_10m_max": [10.0, 10.0],
            }
        },
    )
    advice = generate_advice(prompt)
    assert "降雨機率高達 80%" in advice
    assert "雨具" in advice


def test_generate_advice_hot_weather_mentions_sun_protection():
    prompt = weather_brief.build_ai_prompt(
        "台北",
        {
            "daily": {
                "time": ["2026-08-01", "2026-08-02"],
                "weathercode": [0, 0],
                "temperature_2m_max": [36.0, 35.0],
                "temperature_2m_min": [28.0, 27.0],
                "precipitation_probability_max": [5, 5],
                "precipitation_sum": [0.0, 0.0],
                "windspeed_10m_max": [10.0, 10.0],
            }
        },
    )
    advice = generate_advice(prompt)
    assert "防曬" in advice


def test_generate_advice_strong_wind_mentions_wind():
    prompt = weather_brief.build_ai_prompt(
        "台中",
        {
            "daily": {
                "time": ["2026-08-01", "2026-08-02"],
                "weathercode": [0, 0],
                "temperature_2m_max": [25.0, 25.0],
                "temperature_2m_min": [20.0, 20.0],
                "precipitation_probability_max": [5, 5],
                "precipitation_sum": [0.0, 0.0],
                "windspeed_10m_max": [45.0, 45.0],
            }
        },
    )
    advice = generate_advice(prompt)
    assert "側風" in advice or "招牌" in advice


def test_generate_advice_unrecognized_format_returns_honest_fallback():
    advice = generate_advice("這是一段完全不相關的文字，沒有天氣格式")
    assert "無法生成具體建議" in advice


def test_mock_server_missing_auth_header_returns_401():
    resp = mock_client.post(
        "/v1/chat/completions",
        json={"model": "x", "messages": [{"role": "user", "content": "今天最高溫 30 度"}]},
    )
    assert resp.status_code == 401


def test_mock_server_wrong_api_key_returns_401():
    resp = mock_client.post(
        "/v1/chat/completions",
        json={"model": "x", "messages": [{"role": "user", "content": "測試"}]},
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert resp.status_code == 401


def test_mock_server_correct_key_returns_openai_compatible_shape():
    prompt = weather_brief.build_ai_prompt("台北", SAMPLE_FORECAST)
    resp = mock_client.post(
        "/v1/chat/completions",
        json={
            "model": "mock-weather-advisor",
            "messages": [{"role": "user", "content": prompt}],
        },
        headers={"Authorization": f"Bearer {DEFAULT_API_KEY}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "chat.completion"
    assert "choices" in data and len(data["choices"]) == 1
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert "usage" in data


def test_call_mock_ai_uses_testclient_and_returns_advice_text():
    prompt = weather_brief.build_ai_prompt("台北", SAMPLE_FORECAST)
    advice = weather_brief.call_mock_ai(
        prompt, base_url="", api_key=DEFAULT_API_KEY, client=mock_client
    )
    assert isinstance(advice, str)
    assert len(advice) > 0


def test_call_mock_ai_wrong_key_raises_http_error():
    prompt = weather_brief.build_ai_prompt("台北", SAMPLE_FORECAST)
    with pytest.raises(Exception):
        weather_brief.call_mock_ai(prompt, base_url="", api_key="wrong-key", client=mock_client)


# ---------------------------------------------------------------------------
# main()：端到端（offline 天氣 + AI 服務不可用時的優雅降級）
# ---------------------------------------------------------------------------


def test_main_offline_with_unreachable_ai_server_falls_back_gracefully(capsys):
    # 埠號 8399 假設沒有服務在監聽，驗證 main() 不會炸掉，而是印出說明文字。
    exit_code = weather_brief.main(["--city", "taipei", "--offline", "--ai-port", "8399"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "天氣速報小幫手" in captured.out
    assert "無法連線" in captured.out


def test_main_offline_unknown_city_rejected_by_argparse():
    with pytest.raises(SystemExit):
        weather_brief.main(["--city", "nowhere", "--offline"])
