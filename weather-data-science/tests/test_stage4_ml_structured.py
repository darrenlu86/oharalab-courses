"""測試 stage4_ml_structured：特徵工程正確性（用真實資料驗證邏輯）+
train 函式的小樣本煙霧測試（合成小資料，不追求數字重現，只驗證跑得通、
指標 schema 正確、數值在合理範圍——見 SPEC §7）。
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import matplotlib

matplotlib.use("Agg")

from stage4_ml_structured import features as feat  # noqa: E402
from stage4_ml_structured import train as train_mod  # noqa: E402


@pytest.fixture(scope="module")
def full_features_df():
    return feat.build_features()


# ---------------------------------------------------------------------------
# 特徵工程正確性（真實資料）
# ---------------------------------------------------------------------------


def test_build_features_drops_exactly_90_rows(full_features_df):
    # 3 城市 x (29 天不足以算 rolling_30 + 1 天沒有明天可當目標) = 90 列被丟棄。
    assert len(full_features_df) == 4018 * 3 - 90


def test_lag_1_equals_todays_own_value(full_features_df):
    assert (full_features_df["lag_1_temp_max"] == full_features_df["temperature_2m_max"]).all()
    assert (full_features_df["lag_1_precip"] == full_features_df["precipitation_sum"]).all()


def test_target_temp_is_actually_tomorrows_value(full_features_df):
    taipei = full_features_df[full_features_df["city"] == "taipei"].sort_values("date").reset_index(drop=True)
    assert (
        taipei["target_temp_max_tomorrow"].iloc[:-1].values == taipei["temperature_2m_max"].iloc[1:].values
    ).all()


def test_target_rain_matches_threshold_definition(full_features_df):
    taipei = full_features_df[full_features_df["city"] == "taipei"].sort_values("date").reset_index(drop=True)
    expected = (taipei["precipitation_sum"].iloc[1:].values >= feat.RAIN_THRESHOLD_MM).astype(int)
    assert (taipei["target_rain_tomorrow"].iloc[:-1].values == expected).all()


def test_city_one_hot_columns_sum_to_one(full_features_df):
    onehot_cols = [f"city_{c}" for c in feat.CITIES]
    assert (full_features_df[onehot_cols].sum(axis=1) == 1).all()


def test_no_nan_in_feature_columns(full_features_df):
    assert not full_features_df[feat.FEATURE_COLUMNS].isna().any().any()


def test_require_target_false_leaves_last_day_target_as_na_not_fabricated_false():
    # 踩坑迴歸測試：require_target=False 時,每個城市最後一天沒有「明天」
    # 可以當目標,target_rain_tomorrow 必須是缺值（pd.NA），不能因為
    # `NaN >= 門檻` 的比較運算子預設回傳 False，就被誤標成「明天不會下雨」。
    df = feat.build_features(require_target=False)
    for city in feat.CITIES:
        last_row = df[df["city"] == city].sort_values("date").iloc[-1]
        assert pd.isna(last_row["target_rain_tomorrow"]), (
            f"{city} 最後一天的 target_rain_tomorrow 應為缺值,實際：{last_row['target_rain_tomorrow']}"
        )
        assert pd.isna(last_row["target_temp_max_tomorrow"])


def test_split_train_test_boundaries(full_features_df):
    train_df, test_df = feat.split_train_test(full_features_df)
    assert train_df["date"].max() <= pd.Timestamp("2023-12-31")
    assert test_df["date"].min() > pd.Timestamp("2023-12-31")
    assert len(train_df) + len(test_df) == len(full_features_df)


def test_persistence_rain_baseline_matches_lag1(full_features_df):
    _, test_df = feat.split_train_test(full_features_df)
    pred = feat.persistence_rain_baseline(test_df)
    assert set(pred.unique()) <= {0, 1}
    assert (pred == (test_df["lag_1_precip"] >= feat.RAIN_THRESHOLD_MM).astype(int)).all()


def test_persistence_temp_baseline_equals_lag1_temp(full_features_df):
    _, test_df = feat.split_train_test(full_features_df)
    pred = feat.persistence_temp_baseline(test_df)
    assert (pred == test_df["lag_1_temp_max"]).all()


def test_climatology_rain_baseline_returns_valid_probabilities(full_features_df):
    train_df, test_df = feat.split_train_test(full_features_df)
    probs = feat.climatology_rain_baseline(train_df, test_df)
    assert (probs >= 0).all() and (probs <= 1).all()
    assert len(probs) == len(test_df)


def test_monthly_mean_temp_baseline_within_plausible_range(full_features_df):
    train_df, test_df = feat.split_train_test(full_features_df)
    pred = feat.monthly_mean_temp_baseline(train_df, test_df)
    # 台灣氣溫不會落在這個範圍之外，若跑出來的月均值超出範圍，代表計算邏輯有問題。
    assert (pred > 0).all() and (pred < 45).all()


# ---------------------------------------------------------------------------
# train_classification / train_regression：小樣本煙霧測試（合成資料）
# ---------------------------------------------------------------------------


def _make_synthetic_train_test(n_train=60, n_test=20, seed=42):
    """建構結構正確、數值任意（帶一點訊號）的小樣本資料，只為了驗證
    train_classification/train_regression 兩個函式跑不跑得通、輸出 schema
    對不對，不追求逼近真實資料的統計特性。
    """
    rng = np.random.default_rng(seed)

    def make_df(n, offset):
        temp = rng.uniform(15, 35, n)
        precip = rng.uniform(0, 20, n)
        df = pd.DataFrame(
            {
                "lag_1_temp_max": temp,
                "lag_2_temp_max": temp + rng.normal(0, 1, n),
                "lag_3_temp_max": temp + rng.normal(0, 1, n),
                "lag_1_precip": precip,
                "lag_2_precip": precip + rng.normal(0, 1, n),
                "lag_3_precip": precip + rng.normal(0, 1, n),
                "rolling_7_temp_max": temp + rng.normal(0, 0.5, n),
                "rolling_30_temp_max": temp + rng.normal(0, 0.5, n),
                "rolling_7_precip": precip + rng.normal(0, 0.5, n),
                "rolling_30_precip": precip + rng.normal(0, 0.5, n),
                "month": rng.integers(1, 13, n),
                "temperature_2m_max": temp,
                "city": "taipei",
                "city_taipei": 1,
                "city_taichung": 0,
                "city_kaohsiung": 0,
                "date": pd.date_range("2020-01-01", periods=n, freq="D") + pd.Timedelta(days=offset),
            }
        )
        df["target_rain_tomorrow"] = (precip >= feat.RAIN_THRESHOLD_MM).astype(int)
        df["target_temp_max_tomorrow"] = temp + rng.normal(0, 2, n)
        return df

    train_df = make_df(n_train, offset=0)
    test_df = make_df(n_test, offset=n_train + 100)

    # 確保測試集兩個類別都有出現，否則 roc_auc_score 會報錯。
    test_df.loc[0, "target_rain_tomorrow"] = 0
    test_df.loc[1, "target_rain_tomorrow"] = 1
    return train_df, test_df


def test_train_classification_smoke_runs_and_returns_expected_schema():
    train_df, test_df = _make_synthetic_train_test()
    result = train_mod.train_classification(train_df, test_df)

    assert set(result["results"].keys()) == {
        "baseline_persistence", "baseline_climatology", "logistic_regression", "random_forest",
    }
    for name, metrics in result["results"].items():
        for key in ["accuracy", "precision", "recall", "f1", "roc_auc"]:
            assert key in metrics
            assert 0.0 <= metrics[key] <= 1.0, f"{name}.{key} 超出合理範圍：{metrics[key]}"

    assert len(result["rf_pred"]) == len(test_df)
    assert set(result["feature_importance"].keys()) == set(feat.FEATURE_COLUMNS)


def test_train_regression_smoke_runs_and_returns_expected_schema():
    train_df, test_df = _make_synthetic_train_test()
    result = train_mod.train_regression(train_df, test_df)

    assert set(result["results"].keys()) == {
        "baseline_persistence", "baseline_monthly_mean", "ridge", "random_forest",
    }
    for name, metrics in result["results"].items():
        assert metrics["mae"] >= 0
        assert metrics["rmse"] >= 0
        assert metrics["rmse"] >= metrics["mae"] * 0.9  # RMSE 理論上 >= MAE（容忍浮點誤差）

    assert len(result["rf_pred"]) == len(test_df)
    assert set(result["feature_importance"].keys()) == set(feat.FEATURE_COLUMNS)


# ---------------------------------------------------------------------------
# 六個真實特徵/圖表相關檔案存在性檢查
# ---------------------------------------------------------------------------


def test_four_figure_files_exist_and_non_trivial():
    figures_dir = REPO_ROOT / "stage4_ml_structured" / "figures"
    expected = [
        "fig01_confusion_matrix_rain.png",
        "fig02_feature_importance_rain.png",
        "fig03_feature_importance_temp.png",
        "fig04_regression_actual_vs_predicted.png",
    ]
    for name in expected:
        path = figures_dir / name
        assert path.exists(), f"缺少圖表：{path}"
        assert path.stat().st_size > 5_000
