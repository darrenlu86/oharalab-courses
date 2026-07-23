"""測試 stage2_eda/weather_eda.py：載入/清理/彙整/畫圖函式。

只測函式本身（不 headless 執行 analysis.ipynb——那是另一層驗證，
見 SPEC §7 的 E2E 段落），全部用 repo 裡真實的 data/raw CSV，
不另外造假資料（跟 test_sandbox_site.py 同樣理由：這些函式本來就是
拿真實 committed 資料做輸入）。
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import matplotlib

matplotlib.use("Agg")  # 測試環境不需要互動視窗

from stage2_eda import weather_eda as eda  # noqa: E402


@pytest.fixture(scope="module")
def all_cities_df():
    return eda.load_all_cities()


# ---------------------------------------------------------------------------
# 載入
# ---------------------------------------------------------------------------


def test_load_city_data_has_expected_columns_and_dtypes():
    df = eda.load_city_data("taipei")
    assert pd.api.types.is_datetime64_any_dtype(df["date"])
    assert (df["city"] == "taipei").all()
    assert set(eda.NUMERIC_COLUMNS) <= set(df.columns)
    assert "year" in df.columns and "month" in df.columns


def test_load_all_cities_concatenates_three_cities(all_cities_df):
    assert set(all_cities_df["city"].unique()) == set(eda.CITIES)
    # 每城 4018 筆真實資料（見 docs/DATA_SOURCES.md），三城合併應為其總和。
    assert len(all_cities_df) == 4018 * 3


# ---------------------------------------------------------------------------
# 清理與品質檢查
# ---------------------------------------------------------------------------


def test_missing_value_report_all_zero_on_real_data(all_cities_df):
    report = eda.missing_value_report(all_cities_df)
    assert set(report.keys()) == set(eda.NUMERIC_COLUMNS)
    assert all(v == 0 for v in report.values()), f"真實資料理論上無缺值，實際：{report}"


def test_dtype_check_reports_numeric_types(all_cities_df):
    dtypes = eda.dtype_check(all_cities_df)
    for col, dtype_str in dtypes.items():
        assert "float" in dtype_str or "int" in dtype_str, f"{col} 型別異常：{dtype_str}"


def test_detect_outliers_iqr_returns_subset_with_required_columns(all_cities_df):
    outliers = eda.detect_outliers_iqr(all_cities_df, "precipitation_sum")
    assert len(outliers) > 0  # 降雨右偏分布，一定抓得到離群值
    assert len(outliers) < len(all_cities_df)  # 但不會是全部資料
    assert {"date", "city", "precipitation_sum"} <= set(outliers.columns)


def test_clean_data_does_not_drop_any_row(all_cities_df):
    cleaned, report = eda.clean_data(all_cities_df)
    assert len(cleaned) == len(all_cities_df)  # 刻意不刪除任何列（見 weather_eda.py docstring）
    assert report["row_count"] == len(all_cities_df)
    assert "outlier_counts" in report


def test_add_weather_flags_matches_thresholds():
    df = eda.load_city_data("taipei")
    flagged = eda.add_weather_flags(df)
    assert (flagged.loc[flagged["is_rainy"], "precipitation_sum"] >= eda.RAINY_PRECIP_MM).all()
    assert (flagged.loc[flagged["is_hot"], "temperature_2m_max"] >= eda.HOT_TEMP_C).all()
    # 原始 df 不應被就地修改（add_weather_flags 內部用 .copy()）
    assert "is_rainy" not in df.columns


# ---------------------------------------------------------------------------
# 彙整
# ---------------------------------------------------------------------------


def test_monthly_climatology_has_12_months_and_three_cities(all_cities_df):
    result = eda.monthly_climatology(all_cities_df, "temperature_2m_mean")
    assert list(result.index) == list(range(1, 13))
    assert set(result.columns) == set(eda.CITIES)


def test_yearly_trend_covers_2015_to_2025(all_cities_df):
    result = eda.yearly_trend(all_cities_df, "temperature_2m_mean")
    assert result.index.min() == 2015
    assert result.index.max() == 2025


def test_extreme_events_summary_counts_are_non_negative_and_bounded(all_cities_df):
    summary = eda.extreme_events_summary(all_cities_df)
    assert set(summary.index) == set(eda.CITIES)
    for city in eda.CITIES:
        assert 0 <= summary.loc[city, "extreme_hot_days"] <= summary.loc[city, "total_days"]
        assert 0 <= summary.loc[city, "heavy_rain_days"] <= summary.loc[city, "total_days"]


def test_top_extreme_events_returns_n_rows_sorted_descending(all_cities_df):
    top5 = eda.top_extreme_events(all_cities_df, "precipitation_sum", n=5)
    assert len(top5) == 5
    values = top5["precipitation_sum"].tolist()
    assert values == sorted(values, reverse=True)


def test_correlation_matrix_is_symmetric_with_unit_diagonal(all_cities_df):
    corr = eda.correlation_matrix(all_cities_df)
    assert corr.shape == (len(eda.NUMERIC_COLUMNS), len(eda.NUMERIC_COLUMNS))
    for col in corr.columns:
        assert corr.loc[col, col] == pytest.approx(1.0)
    # 對稱矩陣
    import numpy as np

    assert np.allclose(corr.values, corr.values.T)


def test_precipitation_and_rain_sum_almost_perfectly_correlated(all_cities_df):
    # 兩欄幾乎完全線性相關（絕大多數天氣 precipitation_sum == rain_sum），
    # 但不是恰好 1.0——見下一個測試，有 3 筆真實資料兩者不相等。
    corr = eda.correlation_matrix(all_cities_df)
    assert corr.loc["precipitation_sum", "rain_sum"] > 0.9999


def test_precipitation_sum_and_rain_sum_differ_on_exactly_three_known_rows(all_cities_df):
    # 實測發現（非理論假設）：三筆資料 precipitation_sum > rain_sum，全部落在
    # 2016-01-23~24，與台灣 2016 年 1 月低溫寒流、平地罕見降雪/凍雨事件的時間
    # 吻合，differences 應為當天總降水（含固態/凍雨）扣除純雨量的部分。
    diff = all_cities_df[all_cities_df["precipitation_sum"] != all_cities_df["rain_sum"]]
    assert len(diff) == 3
    assert set(diff["date"].dt.strftime("%Y-%m-%d")) == {"2016-01-23", "2016-01-24"}
    assert (diff["precipitation_sum"] >= diff["rain_sum"]).all()


# ---------------------------------------------------------------------------
# 畫圖：只驗證回傳 Figure、不炸掉，不比對像素內容
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "plot_fn",
    [
        eda.plot_temperature_annual_cycle,
        eda.plot_high_temp_comparison,
        eda.plot_rainfall_seasonal_distribution,
        eda.plot_extreme_events,
        eda.plot_annual_trend,
        eda.plot_correlation_matrix,
    ],
)
def test_plot_functions_return_a_figure_without_raising(all_cities_df, plot_fn):
    import matplotlib.figure

    fig = plot_fn(all_cities_df)
    assert isinstance(fig, matplotlib.figure.Figure)
    import matplotlib.pyplot as plt

    plt.close(fig)


def test_six_figure_files_exist_and_are_non_trivial_size():
    figures_dir = REPO_ROOT / "stage2_eda" / "figures"
    expected = [
        "fig01_temperature_annual_cycle.png",
        "fig02_high_temp_comparison.png",
        "fig03_rainfall_seasonal_distribution.png",
        "fig04_extreme_events.png",
        "fig05_annual_trend.png",
        "fig06_correlation_matrix.png",
    ]
    for name in expected:
        path = figures_dir / name
        assert path.exists(), f"缺少圖表檔案：{path}"
        assert path.stat().st_size > 5_000, f"{name} 檔案過小，可能是空圖或壞圖：{path.stat().st_size} bytes"
