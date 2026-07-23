"""訓練並評估 stage4 兩個任務：明日降雨分類 + 明日高溫回歸。

用法：
    venv/bin/python -m stage4_ml_structured.train

會印出完整的指標比較表（含基準線），並把模型存進
`stage4_ml_structured/models/*.joblib`（gitignored，本腳本可重新產生）、
圖表存進 `stage4_ml_structured/figures/*.png`（committed）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    precision_score,
    recall_score,
    roc_auc_score,
    root_mean_squared_error,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stage4_ml_structured.features import (  # noqa: E402
    FEATURE_COLUMNS,
    build_features,
    climatology_rain_baseline,
    monthly_mean_temp_baseline,
    persistence_rain_baseline,
    persistence_temp_baseline,
    split_train_test,
)

MODELS_DIR = Path(__file__).resolve().parent / "models"
FIGURES_DIR = Path(__file__).resolve().parent / "figures"
MODEL_VERSION = "v1"

RANDOM_STATE = 42


def train_classification(train_df: pd.DataFrame, test_df: pd.DataFrame) -> dict:
    X_train, y_train = train_df[FEATURE_COLUMNS], train_df["target_rain_tomorrow"]
    X_test, y_test = test_df[FEATURE_COLUMNS], test_df["target_rain_tomorrow"]

    log_reg = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=RANDOM_STATE))
    log_reg.fit(X_train, y_train)

    rf = RandomForestClassifier(n_estimators=300, max_depth=10, random_state=RANDOM_STATE, n_jobs=-1)
    rf.fit(X_train, y_train)

    persistence_pred = persistence_rain_baseline(test_df)
    climatology_prob = climatology_rain_baseline(train_df, test_df)
    climatology_pred = (climatology_prob >= 0.5).astype(int)

    results = {}
    predictions = {
        "baseline_persistence": (persistence_pred, persistence_pred),  # 沒有機率，用 label 當 prob
        "baseline_climatology": (climatology_pred, climatology_prob),
        "logistic_regression": (log_reg.predict(X_test), log_reg.predict_proba(X_test)[:, 1]),
        "random_forest": (rf.predict(X_test), rf.predict_proba(X_test)[:, 1]),
    }
    for name, (pred, prob) in predictions.items():
        results[name] = {
            "accuracy": accuracy_score(y_test, pred),
            "precision": precision_score(y_test, pred, zero_division=0),
            "recall": recall_score(y_test, pred, zero_division=0),
            "f1": f1_score(y_test, pred, zero_division=0),
            "roc_auc": roc_auc_score(y_test, prob),
        }

    return {
        "results": results,
        "models": {"logistic_regression": log_reg, "random_forest": rf},
        "y_test": y_test,
        "rf_pred": predictions["random_forest"][0],
        "feature_importance": dict(zip(FEATURE_COLUMNS, rf.feature_importances_)),
    }


def train_regression(train_df: pd.DataFrame, test_df: pd.DataFrame) -> dict:
    X_train, y_train = train_df[FEATURE_COLUMNS], train_df["target_temp_max_tomorrow"]
    X_test, y_test = test_df[FEATURE_COLUMNS], test_df["target_temp_max_tomorrow"]

    ridge = make_pipeline(StandardScaler(), Ridge(alpha=1.0, random_state=RANDOM_STATE))
    ridge.fit(X_train, y_train)

    rf = RandomForestRegressor(n_estimators=300, max_depth=10, random_state=RANDOM_STATE, n_jobs=-1)
    rf.fit(X_train, y_train)

    predictions = {
        "baseline_persistence": persistence_temp_baseline(test_df),
        "baseline_monthly_mean": monthly_mean_temp_baseline(train_df, test_df),
        "ridge": ridge.predict(X_test),
        "random_forest": rf.predict(X_test),
    }

    results = {}
    for name, pred in predictions.items():
        results[name] = {
            "mae": mean_absolute_error(y_test, pred),
            "rmse": root_mean_squared_error(y_test, pred),
        }

    return {
        "results": results,
        "models": {"ridge": ridge, "random_forest": rf},
        "y_test": y_test,
        "rf_pred": predictions["random_forest"],
        "feature_importance": dict(zip(FEATURE_COLUMNS, rf.feature_importances_)),
    }


def print_classification_table(results: dict) -> None:
    print(f"{'模型':<22}{'accuracy':>10}{'precision':>11}{'recall':>9}{'f1':>8}{'roc_auc':>9}")
    for name, m in results.items():
        print(f"{name:<22}{m['accuracy']:>10.3f}{m['precision']:>11.3f}{m['recall']:>9.3f}{m['f1']:>8.3f}{m['roc_auc']:>9.3f}")


def print_regression_table(results: dict) -> None:
    print(f"{'模型':<22}{'MAE (°C)':>10}{'RMSE (°C)':>11}")
    for name, m in results.items():
        print(f"{name:<22}{m['mae']:>10.3f}{m['rmse']:>11.3f}")


def save_figures(clf_result: dict, reg_result: dict) -> None:
    import matplotlib.pyplot as plt

    from common.fonts import setup_chinese_font

    setup_chinese_font()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    # 圖一：混淆矩陣（RandomForestClassifier）
    cm = confusion_matrix(clf_result["y_test"], clf_result["rf_pred"])
    fig, ax = plt.subplots(figsize=(5, 4.5))
    im = ax.imshow(cm, cmap="Blues")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center", fontsize=14)
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["不下雨", "下雨"])
    ax.set_yticklabels(["不下雨", "下雨"])
    ax.set_xlabel("預測")
    ax.set_ylabel("實際")
    ax.set_title("明日降雨分類混淆矩陣（RandomForest，測試集）")
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig01_confusion_matrix_rain.png", dpi=100)
    plt.close(fig)

    # 圖二：分類特徵重要度
    fig, ax = plt.subplots(figsize=(8, 5))
    items = sorted(clf_result["feature_importance"].items(), key=lambda x: x[1])
    ax.barh([k for k, _ in items], [v for _, v in items], color="#4472c4")
    ax.set_title("明日降雨分類：特徵重要度（RandomForest）")
    ax.set_xlabel("重要度")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig02_feature_importance_rain.png", dpi=100)
    plt.close(fig)

    # 圖三：回歸特徵重要度
    fig, ax = plt.subplots(figsize=(8, 5))
    items = sorted(reg_result["feature_importance"].items(), key=lambda x: x[1])
    ax.barh([k for k, _ in items], [v for _, v in items], color="#c78d1e")
    ax.set_title("明日高溫回歸：特徵重要度（RandomForest）")
    ax.set_xlabel("重要度")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig03_feature_importance_temp.png", dpi=100)
    plt.close(fig)

    # 圖四：回歸實際 vs 預測散佈圖
    fig, ax = plt.subplots(figsize=(6, 6))
    y_test = reg_result["y_test"]
    ax.scatter(y_test, reg_result["rf_pred"], s=6, alpha=0.4, color="#c78d1e")
    lims = [y_test.min(), y_test.max()]
    ax.plot(lims, lims, color="#c0392b", linewidth=1, linestyle="--", label="完美預測線")
    ax.set_xlabel("實際明日最高溫（°C）")
    ax.set_ylabel("預測明日最高溫（°C）")
    ax.set_title("明日高溫回歸：實際 vs 預測（RandomForest，測試集）")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig04_regression_actual_vs_predicted.png", dpi=100)
    plt.close(fig)


def main() -> int:
    print("載入資料並建構特徵...")
    df = build_features()
    train_df, test_df = split_train_test(df)
    print(f"訓練集：{len(train_df)} 列（{train_df['date'].min().date()} ~ {train_df['date'].max().date()}）")
    print(f"測試集：{len(test_df)} 列（{test_df['date'].min().date()} ~ {test_df['date'].max().date()}）")
    print()

    print("=== 任務 A：明日降雨分類 ===")
    clf_result = train_classification(train_df, test_df)
    print_classification_table(clf_result["results"])
    print()

    print("=== 任務 B：明日高溫回歸 ===")
    reg_result = train_regression(train_df, test_df)
    print_regression_table(reg_result["results"])
    print()

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf_result["models"]["logistic_regression"], MODELS_DIR / f"rain_logistic_regression_{MODEL_VERSION}.joblib")
    joblib.dump(clf_result["models"]["random_forest"], MODELS_DIR / f"rain_random_forest_{MODEL_VERSION}.joblib")
    joblib.dump(reg_result["models"]["ridge"], MODELS_DIR / f"temp_ridge_{MODEL_VERSION}.joblib")
    joblib.dump(reg_result["models"]["random_forest"], MODELS_DIR / f"temp_random_forest_{MODEL_VERSION}.joblib")
    print(f"模型已存至 {MODELS_DIR}/（gitignored，本腳本可重新產生）")

    save_figures(clf_result, reg_result)
    print(f"圖表已存至 {FIGURES_DIR}/")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
