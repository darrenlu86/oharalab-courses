"""v1（僅 lag 特徵）vs v2（+rolling/月份）模型迭代比較，餵給 report.md 的
「落地效能評估與迭代優化」數字來源。

這支腳本不是 app.py 或 pipeline/ 的一部分——儀表板本身只用 v2（也就是
stage4_ml_structured 訓練出來的模型)。這裡單獨重新訓練一版「刻意精簡」
的 v1（只用 lag_1/2/3 特徵 + 城市 one-hot，拿掉 rolling 均值與月份),
跟 v2 用同一份訓練/測試切分、同樣的 RandomForest 超參數比較,唯一變數是
特徵集合——這樣才能把「加 rolling/月份到底有沒有幫助」這個問題回答乾淨,
不會被其他變因（切分方式、模型種類）干擾。

用法：
    venv/bin/python -m stage6_system.model_iteration_report
"""

from __future__ import annotations

import sys
from pathlib import Path

from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    precision_score,
    recall_score,
    roc_auc_score,
    root_mean_squared_error,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stage4_ml_structured.features import CITIES, build_features, split_train_test  # noqa: E402
from stage4_ml_structured.train import RANDOM_STATE  # noqa: E402

V1_FEATURE_COLUMNS = (
    ["lag_1_temp_max", "lag_2_temp_max", "lag_3_temp_max"]
    + ["lag_1_precip", "lag_2_precip", "lag_3_precip"]
    + [f"city_{c}" for c in CITIES]
)
V2_FEATURE_COLUMNS = V1_FEATURE_COLUMNS + [
    "rolling_7_temp_max", "rolling_30_temp_max", "rolling_7_precip", "rolling_30_precip", "month",
]


def _train_eval_classification(train_df, test_df, feature_columns) -> dict:
    X_train, y_train = train_df[feature_columns], train_df["target_rain_tomorrow"]
    X_test, y_test = test_df[feature_columns], test_df["target_rain_tomorrow"]
    model = RandomForestClassifier(n_estimators=300, max_depth=10, random_state=RANDOM_STATE, n_jobs=-1)
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    proba = model.predict_proba(X_test)[:, 1]
    return {
        "accuracy": accuracy_score(y_test, pred),
        "precision": precision_score(y_test, pred, zero_division=0),
        "recall": recall_score(y_test, pred, zero_division=0),
        "f1": f1_score(y_test, pred, zero_division=0),
        "roc_auc": roc_auc_score(y_test, proba),
    }


def _train_eval_regression(train_df, test_df, feature_columns) -> dict:
    X_train, y_train = train_df[feature_columns], train_df["target_temp_max_tomorrow"]
    X_test, y_test = test_df[feature_columns], test_df["target_temp_max_tomorrow"]
    model = RandomForestRegressor(n_estimators=300, max_depth=10, random_state=RANDOM_STATE, n_jobs=-1)
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    return {"mae": mean_absolute_error(y_test, pred), "rmse": root_mean_squared_error(y_test, pred)}


def run_comparison() -> dict:
    df = build_features()
    train_df, test_df = split_train_test(df)

    return {
        "classification": {
            "v1_lag_only": _train_eval_classification(train_df, test_df, V1_FEATURE_COLUMNS),
            "v2_plus_rolling_month": _train_eval_classification(train_df, test_df, V2_FEATURE_COLUMNS),
        },
        "regression": {
            "v1_lag_only": _train_eval_regression(train_df, test_df, V1_FEATURE_COLUMNS),
            "v2_plus_rolling_month": _train_eval_regression(train_df, test_df, V2_FEATURE_COLUMNS),
        },
        "v1_feature_count": len(V1_FEATURE_COLUMNS),
        "v2_feature_count": len(V2_FEATURE_COLUMNS),
    }


def main() -> int:
    result = run_comparison()
    print(f"v1 特徵數：{result['v1_feature_count']}（{V1_FEATURE_COLUMNS}）")
    print(f"v2 特徵數：{result['v2_feature_count']}（v1 + rolling_7/30 + month）")
    print()
    print("=== 分類任務（明日降雨）===")
    print(f"{'版本':<24}{'accuracy':>10}{'precision':>11}{'recall':>9}{'f1':>8}{'roc_auc':>9}")
    for name, m in result["classification"].items():
        print(f"{name:<24}{m['accuracy']:>10.3f}{m['precision']:>11.3f}{m['recall']:>9.3f}{m['f1']:>8.3f}{m['roc_auc']:>9.3f}")
    print()
    print("=== 回歸任務（明日高溫）===")
    print(f"{'版本':<24}{'MAE (°C)':>10}{'RMSE (°C)':>11}")
    for name, m in result["regression"].items():
        print(f"{name:<24}{m['mae']:>10.3f}{m['rmse']:>11.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
