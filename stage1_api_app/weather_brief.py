"""CLI「天氣速報小幫手」：串接 Open-Meteo forecast API + 本地 mock AI API。

用法：
    venv/bin/python -m stage1_api_app.weather_brief --city taipei
    venv/bin/python -m stage1_api_app.weather_brief --city taipei --offline
    venv/bin/python -m stage1_api_app.weather_brief --city taichung --ai-port 8331

執行前請先在另一個終端機啟動 mock AI 服務（--offline 也需要，因為
--offline 只影響天氣資料來源，不影響 AI 建議來源）：
    venv/bin/python -m uvicorn stage1_api_app.mock_ai_server:app --port 8331

流程：
    1. 取得未來兩天（今天/明天）天氣預報 —— 預設呼叫 Open-Meteo forecast
       API（真實、免金鑰）；`--offline` 改讀 stage1_api_app/samples/ 裡
       擷取好的真實回應 JSON（附擷取時間，見 samples/README.md）。
    2. 把預報整理成固定格式的文字，POST 給本地 mock AI 服務取得穿搭/
       出行建議（OpenAI Chat Completions 相容格式）。
    3. 排版輸出成一份文字速報。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

SAMPLES_DIR = Path(__file__).resolve().parent / "samples"

FORECAST_API_URL = "https://api.open-meteo.com/v1/forecast"

# 城市座標與中文名稱，與 SPEC §3.1/common 共用的三城市一致。
CITY_INFO = {
    "taipei": {"name_zh": "台北", "lat": 25.0330, "lon": 121.5654},
    "taichung": {"name_zh": "台中", "lat": 24.1477, "lon": 120.6736},
    "kaohsiung": {"name_zh": "高雄", "lat": 22.6273, "lon": 120.3014},
}

DAILY_VARS = [
    "weathercode",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_probability_max",
    "precipitation_sum",
    "windspeed_10m_max",
]

TIMEOUT_SECONDS = 10.0
MAX_RETRIES = 2

DEFAULT_AI_PORT = 8331
DEFAULT_AI_API_KEY = "mock-weather-advisor-demo-key"  # 需與 mock_ai_server.py 的預設值一致

# WMO 天氣代碼對照表（Open-Meteo 文件 https://open-meteo.com/en/docs 採用的
# 標準 WMO 4677 分類），只列本課程用得到的代碼，非窮舉全部代碼。
WEATHER_CODE_DESC = {
    0: "晴朗",
    1: "大致晴朗",
    2: "局部多雲",
    3: "多雲",
    45: "有霧",
    48: "霧淞",
    51: "毛毛雨（弱）",
    53: "毛毛雨（中）",
    55: "毛毛雨（強）",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    80: "陣雨（弱）",
    81: "陣雨（中）",
    82: "陣雨（強，猛烈）",
    95: "雷雨",
    96: "雷雨（伴隨小冰雹）",
    99: "雷雨（伴隨大冰雹）",
}


def weather_code_desc(code: int) -> str:
    return WEATHER_CODE_DESC.get(code, f"未知代碼({code})")


# ---------------------------------------------------------------------------
# 1. 取得天氣預報
# ---------------------------------------------------------------------------


def fetch_forecast(city: str, session=None, timeout: float = TIMEOUT_SECONDS) -> dict:
    """呼叫 Open-Meteo forecast API 取得指定城市未來兩天預報。

    `session` 可注入任何有 `.get(url, params=..., timeout=...)` 介面的物件
    （預設用 `requests` 模組本身），方便測試時換成假的 session，不必真的
    連外網。失敗（逾時/非 200/JSON 解析失敗）會重試最多 MAX_RETRIES 次。
    """
    if session is None:
        session = requests
    info = CITY_INFO[city]
    params = {
        "latitude": info["lat"],
        "longitude": info["lon"],
        "daily": ",".join(DAILY_VARS),
        "timezone": "Asia/Taipei",
        "forecast_days": 2,
    }

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            resp = session.get(FORECAST_API_URL, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            print(f"  [警告] {city} forecast 第 {attempt} 次請求失敗：{exc}", file=sys.stderr)
            if attempt <= MAX_RETRIES:
                time.sleep(1.0)
    raise RuntimeError(f"{city} forecast 抓取失敗，已重試 {MAX_RETRIES} 次：{last_error}")


def load_offline_forecast(city: str) -> dict:
    """讀 stage1_api_app/samples/forecast_{city}.json（真實 API 回應存檔）。"""
    path = SAMPLES_DIR / f"forecast_{city}.json"
    if not path.exists():
        raise FileNotFoundError(f"找不到離線樣本：{path}（--offline 模式需要這份檔案）")
    return json.loads(path.read_text(encoding="utf-8"))


def get_forecast(city: str, offline: bool = False, session=None) -> dict:
    if offline:
        return load_offline_forecast(city)
    return fetch_forecast(city, session=session)


# ---------------------------------------------------------------------------
# 2. 呼叫本地 mock AI 服務
# ---------------------------------------------------------------------------


def build_ai_prompt(city_name_zh: str, forecast: dict) -> str:
    """把 forecast JSON 整理成固定格式文字，餵給 mock AI 服務解析。

    格式必須跟 mock_ai_server.py 的 TODAY_PATTERN/TOMORROW_PATTERN 對得上，
    這是兩邊之間隱含的契約——真實 LLM 不需要這麼死板的格式，但這支
    mock 服務是規則式的，格式必須固定。
    """
    daily = forecast["daily"]
    dates = daily["time"]
    lines = [f"以下是{city_name_zh}接下來兩天的天氣預報："]
    labels = ["今天", "明天"]
    for i, label in enumerate(labels[: len(dates)]):
        desc = weather_code_desc(daily["weathercode"][i])
        lines.append(
            f"{label}（{dates[i]}）：天氣狀況｜{desc}，"
            f"最高溫 {daily['temperature_2m_max'][i]} 度，"
            f"最低溫 {daily['temperature_2m_min'][i]} 度，"
            f"降雨機率 {daily['precipitation_probability_max'][i]}%，"
            f"最大風速 {daily['windspeed_10m_max'][i]} km/h。"
        )
    lines.append("請根據以上資訊給出穿搭建議與出行建議。")
    return "\n".join(lines)


def call_mock_ai(prompt: str, base_url: str, api_key: str, client=None, timeout: float = TIMEOUT_SECONDS) -> str:
    """POST 到 mock AI 服務的 /v1/chat/completions，回傳建議文字。

    `client` 可以是 `requests`（預設，真的連 localhost）或 FastAPI
    `TestClient` 實例（測試時用，兩者都有相容的 `.post(url, json=, headers=,
    timeout=)` 介面，`TestClient.post` 會忽略多餘的 timeout kwarg）。
    """
    if client is None:
        client = requests
    resp = client.post(
        f"{base_url}/v1/chat/completions",
        json={
            "model": "mock-weather-advisor",
            "messages": [
                {"role": "system", "content": "你是天氣穿搭與出行建議助理。"},
                {"role": "user", "content": prompt},
            ],
        },
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# 3. 排版輸出
# ---------------------------------------------------------------------------


def build_briefing_text(city_name_zh: str, forecast: dict, advice: str, source_label: str) -> str:
    daily = forecast["daily"]
    dates = daily["time"]
    labels = ["今天", "明天"]

    lines = [
        "=" * 44,
        f"  天氣速報小幫手｜{city_name_zh}",
        "=" * 44,
        f"（資料來源：{source_label}）",
        "",
    ]
    for i, label in enumerate(labels[: len(dates)]):
        desc = weather_code_desc(daily["weathercode"][i])
        lines.append(f"【{label}】{dates[i]}")
        lines.append(f"  天氣狀況：{desc}")
        lines.append(
            f"  溫度：{daily['temperature_2m_min'][i]} ~ {daily['temperature_2m_max'][i]} 度"
        )
        lines.append(f"  降雨機率：{daily['precipitation_probability_max'][i]}%（預估降雨量 {daily['precipitation_sum'][i]} mm）")
        lines.append(f"  最大風速：{daily['windspeed_10m_max'][i]} km/h")
        lines.append("")

    lines.append("【AI 建議】（本地 mock 服務規則式生成，非真實 LLM）")
    lines.append(f"  {advice}")
    lines.append("")
    lines.append("=" * 44)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="天氣速報小幫手：Open-Meteo forecast + 本地 mock AI 建議。")
    parser.add_argument("--city", default="taipei", choices=list(CITY_INFO.keys()), help="城市 slug")
    parser.add_argument("--offline", action="store_true", help="天氣資料改用 stage1_api_app/samples/ 裡的離線樣本")
    parser.add_argument("--ai-host", default="127.0.0.1", help="mock AI 服務主機（預設 127.0.0.1）")
    parser.add_argument("--ai-port", type=int, default=DEFAULT_AI_PORT, help="mock AI 服務埠號（預設 8331）")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    city_name_zh = CITY_INFO[args.city]["name_zh"]

    try:
        forecast = get_forecast(args.city, offline=args.offline)
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"取得天氣預報失敗：{exc}", file=sys.stderr)
        return 1

    source_label = (
        "stage1_api_app/samples/（離線樣本，非本次即時抓取）"
        if args.offline
        else "Open-Meteo forecast API（即時）"
    )

    prompt = build_ai_prompt(city_name_zh, forecast)
    api_key = os.environ.get("MOCK_AI_API_KEY", DEFAULT_AI_API_KEY)
    base_url = f"http://{args.ai_host}:{args.ai_port}"

    try:
        advice = call_mock_ai(prompt, base_url=base_url, api_key=api_key)
    except requests.RequestException as exc:
        advice = (
            f"(AI 建議服務目前無法連線：{exc}；"
            f"請確認 mock_ai_server 是否已啟動於 {base_url}，"
            "啟動指令：venv/bin/python -m uvicorn stage1_api_app.mock_ai_server:app --port 8331)"
        )

    print(build_briefing_text(city_name_zh, forecast, advice, source_label))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
