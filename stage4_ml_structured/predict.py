"""載入已訓練模型，對單一城市/日期做推論（示範「訓練好的模型怎麼被使用」）。

用法：
    venv/bin/python -m stage4_ml_structured.predict --city taipei --date 2025-06-15

`--date` 是「今天」（模型會用這天為止的歷史資料，預測「明天」的降雨機率
與最高溫）。如果 `data/raw` 裡剛好有這天的隔天資料，會一併印出實際值方便
你比對；沒有的話（例如你問的是資料集最後一天）就只印預測值，這是正常情況，
不是錯誤。

執行前請先跑過 `venv/bin/python -m stage4_ml_structured.train`（本腳本會
載入它產生的 *.joblib 模型）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stage2_eda.weather_eda import load_all_cities  # noqa: E402
from stage4_ml_structured.features import FEATURE_COLUMNS, RAIN_THRESHOLD_MM, build_features  # noqa: E402
from stage4_ml_structured.train import MODELS_DIR, MODEL_VERSION  # noqa: E402


def load_models(models_dir: Path = MODELS_DIR, version: str = MODEL_VERSION) -> dict:
    paths = {
        "rain": models_dir / f"rain_random_forest_{version}.joblib",
        "temp": models_dir / f"temp_random_forest_{version}.joblib",
    }
    missing = [name for name, p in paths.items() if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"找不到模型檔案 {missing}，請先執行："
            "venv/bin/python -m stage4_ml_structured.train"
        )
    return {name: joblib.load(p) for name, p in paths.items()}


def get_feature_row(city: str, date: str) -> pd.Series:
    """回傳指定城市/日期（視為「今天」）的一列特徵，供模型推論用。"""
    df = build_features(require_target=False)
    match = df[(df["city"] == city) & (df["date"] == pd.Timestamp(date))]
    if match.empty:
        raise ValueError(
            f"找不到 {city} {date} 的特徵資料——可能是資料範圍不足（每個城市開頭 29 天"
            "無法算出 rolling_30，或該城市/日期不在 data/raw 範圍內）。"
        )
    return match.iloc[0]


def predict(city: str, date: str, models: dict | None = None) -> dict:
    if models is None:
        models = load_models()
    row = get_feature_row(city, date)
    X = row[FEATURE_COLUMNS].to_frame().T.astype(float)

    rain_prob = float(models["rain"].predict_proba(X)[0, 1])
    rain_label = int(rain_prob >= 0.5)
    temp_pred = float(models["temp"].predict(X)[0])

    result = {
        "city": city,
        "date": date,
        "rain_prob": rain_prob,
        "rain_label": rain_label,
        "temp_pred": temp_pred,
    }
    if pd.notna(row.get("target_rain_tomorrow")):
        result["actual_rain_label"] = int(row["target_rain_tomorrow"])
    if pd.notna(row.get("target_temp_max_tomorrow")):
        result["actual_temp"] = float(row["target_temp_max_tomorrow"])
    return result


def format_result(result: dict) -> str:
    lines = [
        f"城市：{result['city']}　基準日：{result['date']}（預測隔天）",
        f"降雨機率：{result['rain_prob']:.1%}（預測標籤：{'下雨' if result['rain_label'] else '不下雨'}，"
        f"門檻 precipitation_sum >= {RAIN_THRESHOLD_MM}mm）",
        f"最高溫預測：{result['temp_pred']:.1f}°C",
    ]
    if "actual_rain_label" in result:
        lines.append(f"實際降雨標籤：{'下雨' if result['actual_rain_label'] else '不下雨'}")
    if "actual_temp" in result:
        lines.append(f"實際最高溫：{result['actual_temp']:.1f}°C")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="用已訓練模型預測指定城市/日期的隔天降雨與高溫")
    parser.add_argument("--city", required=True, choices=["taipei", "taichung", "kaohsiung"])
    parser.add_argument("--date", required=True, help="YYYY-MM-DD，視為「今天」")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = predict(args.city, args.date)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[錯誤] {exc}", file=sys.stderr)
        return 1
    print(format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
