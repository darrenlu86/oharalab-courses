"""從 Open-Meteo Historical Weather API 抓取台灣三城市歷史天氣資料。

用法：
    venv/bin/python -m scripts.fetch_weather_data
    venv/bin/python -m scripts.fetch_weather_data --cities taipei taichung
    venv/bin/python -m scripts.fetch_weather_data --start 2020-01-01 --end 2020-12-31

資料來源：https://archive-api.open-meteo.com/v1/archive（ERA5 再分析網格資料，CC BY 4.0）。
逐城市抓取，逾時 30 秒、失敗重試 2 次、城市間 sleep 1 秒（避免造成 API 負擔）。
輸出一城一 CSV，欄名照 API 回應原樣（首欄改名為 date）。
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.paths import RAW_DIR  # noqa: E402

API_URL = "https://archive-api.open-meteo.com/v1/archive"

# 城市座標（slug -> (latitude, longitude)），照 SPEC §3.1
CITY_COORDS = {
    "taipei": (25.0330, 121.5654),
    "taichung": (24.1477, 120.6736),
    "kaohsiung": (22.6273, 120.3014),
}

# SPEC §3.1 列出的 daily 變數清單。實際請求前已用一段短區間（2025-06-01~03）
# 對 API 實測過，十個欄位全部有效回應，故本清單未做刪減。
# 若未來 API 改版導致某欄消失，請求會回 400，須手動移除該欄並在
# docs/DATA_SOURCES.md 記錄。
DAILY_VARS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
    "rain_sum",
    "precipitation_hours",
    "windspeed_10m_max",
    "windgusts_10m_max",
    "winddirection_10m_dominant",
    "shortwave_radiation_sum",
]

TIMEOUT_SECONDS = 30
MAX_RETRIES = 2  # 首次嘗試之外再重試 2 次，總共最多 3 次
SLEEP_BETWEEN_CITIES = 1.0


def fetch_city(city: str, start: str, end: str, daily_vars: list[str]) -> dict:
    """呼叫 Open-Meteo archive API 取得單一城市的歷史每日資料。

    回傳整個解析後的 JSON dict（包含 latitude/longitude/daily 等欄位）。
    失敗時重試最多 MAX_RETRIES 次，逾時或非 200 都視為失敗。
    """
    lat, lon = CITY_COORDS[city]
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "daily": ",".join(daily_vars),
        "timezone": "Asia/Taipei",
    }

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 2):  # 1 次首試 + MAX_RETRIES 次重試
        try:
            resp = requests.get(API_URL, params=params, timeout=TIMEOUT_SECONDS)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            print(
                f"  [警告] {city} 第 {attempt} 次請求失敗：{exc}",
                file=sys.stderr,
            )
            if attempt <= MAX_RETRIES:
                time.sleep(1.0)
    raise RuntimeError(f"{city} 抓取失敗，已重試 {MAX_RETRIES} 次：{last_error}")


def write_csv(city: str, payload: dict, daily_vars: list[str], out_dir: Path) -> tuple[int, dict[str, int]]:
    """把 API 回應寫成 CSV，首欄 date，其餘欄名照 API 原樣。

    回傳 (row 數, {欄名: 缺值數} )。
    """
    daily = payload["daily"]
    times = daily["time"]
    fieldnames = ["date"] + daily_vars

    out_path = out_dir / f"{city}.csv"
    missing_counts = {var: 0 for var in daily_vars}

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(fieldnames)
        for i, date in enumerate(times):
            row = [date]
            for var in daily_vars:
                value = daily[var][i]
                if value is None:
                    missing_counts[var] += 1
                row.append(value if value is not None else "")
            writer.writerow(row)

    return len(times), missing_counts


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="從 Open-Meteo Historical Weather API 抓取台灣城市歷史天氣資料。"
    )
    parser.add_argument(
        "--cities",
        nargs="+",
        default=["taipei", "taichung", "kaohsiung"],
        choices=list(CITY_COORDS.keys()),
        help="要抓取的城市 slug（預設三城市全抓）",
    )
    parser.add_argument("--start", default="2015-01-01", help="起始日期 YYYY-MM-DD")
    parser.add_argument("--end", default="2025-12-31", help="結束日期 YYYY-MM-DD")
    parser.add_argument(
        "--out",
        default=str(RAW_DIR),
        help="輸出目錄（預設 data/raw/）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    daily_vars = list(DAILY_VARS)

    for idx, city in enumerate(args.cities):
        print(f"抓取 {city}（{args.start} ~ {args.end}）...")
        payload = fetch_city(city, args.start, args.end, daily_vars)

        returned_lat = payload.get("latitude")
        returned_lon = payload.get("longitude")
        requested_lat, requested_lon = CITY_COORDS[city]
        print(
            f"  請求座標 ({requested_lat}, {requested_lon}) -> "
            f"API 回傳網格座標 ({returned_lat}, {returned_lon})"
        )

        row_count, missing_counts = write_csv(city, payload, daily_vars, out_dir)
        print(f"  {city}.csv 寫入完成，共 {row_count} 列")

        missing_report = {k: v for k, v in missing_counts.items() if v > 0}
        if missing_report:
            print(f"  缺值統計：{missing_report}")
        else:
            print("  缺值統計：無缺值")

        if idx < len(args.cities) - 1:
            time.sleep(SLEEP_BETWEEN_CITIES)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
