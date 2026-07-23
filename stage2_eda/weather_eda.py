"""stage2_eda 的核心邏輯：載入/清理/彙整/畫圖函式。

`analysis.ipynb` 只 import 這裡的函式並串成分析敘事（載入→清理→探索→
畫圖→解讀→結論），不在 notebook 裡重寫任何一行資料處理邏輯——這樣
`tests/test_stage2_eda.py` 才能直接測函式本身，不需要 headless 執行整份
notebook才能驗證邏輯正確性（headless 執行 notebook 由另一個測試/驗證
流程負責，見 SPEC §7）。

天氣分類門檻（雨天 `precipitation_sum >= 1.0mm`、高溫日
`temperature_2m_max >= 33.0`C`）跟 `scripts/generate_synthetic.py`／
stage4 的定義一致，全課程統一，不要各階段各自訂一套。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.paths import RAW_DIR  # noqa: E402

CITIES = ["taipei", "taichung", "kaohsiung"]
CITY_NAME_ZH = {"taipei": "台北", "taichung": "台中", "kaohsiung": "高雄"}

# 與 scripts/generate_synthetic.py 一致的門檻，全課程共用同一套定義。
RAINY_PRECIP_MM = 1.0
HOT_TEMP_C = 33.0

NUMERIC_COLUMNS = [
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


# ---------------------------------------------------------------------------
# 載入
# ---------------------------------------------------------------------------


def load_city_data(city: str, raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """讀單一城市 CSV，把 date 轉成 datetime，加上 year/month 衍生欄位。"""
    path = raw_dir / f"{city}.csv"
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df["city"] = city
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    return df


def load_all_cities(cities: list[str] = CITIES, raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """讀三城市 CSV 並垂直合併成一份長格式 DataFrame（多一欄 city）。"""
    frames = [load_city_data(city, raw_dir=raw_dir) for city in cities]
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# 清理與資料品質檢查
# ---------------------------------------------------------------------------


def missing_value_report(df: pd.DataFrame, columns: list[str] = NUMERIC_COLUMNS) -> dict[str, int]:
    """回傳各欄位缺值數量的 dict，全部欄位都會出現在結果裡（即使是 0）。"""
    return {col: int(df[col].isna().sum()) for col in columns if col in df.columns}


def detect_outliers_iqr(df: pd.DataFrame, column: str, k: float = 1.5) -> pd.DataFrame:
    """用 IQR 方法找出某欄位的離群值列（不刪除，只回傳供人工檢視）。

    回傳的 DataFrame 只包含超出 [Q1 - k*IQR, Q3 + k*IQR] 範圍的列，
    附上 date/city/該欄位值，方便在 notebook 裡列出來看是不是真實極端天氣
    （例如颱風）而不是資料錯誤。
    """
    q1, q3 = df[column].quantile([0.25, 0.75])
    iqr = q3 - q1
    lower, upper = q1 - k * iqr, q3 + k * iqr
    mask = (df[column] < lower) | (df[column] > upper)
    cols = [c for c in ["date", "city", column] if c in df.columns]
    return df.loc[mask, cols].sort_values(column)


def dtype_check(df: pd.DataFrame, columns: list[str] = NUMERIC_COLUMNS) -> dict[str, str]:
    """回傳各欄位實際 dtype 的字串表示,用來確認數值欄位真的被解析成數字
    而不是字串（CSV 讀進來最常見的地雷)。
    """
    return {col: str(df[col].dtype) for col in columns if col in df.columns}


def clean_data(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """跑一輪資料品質檢查,回傳（原樣資料,檢查報告 dict）。

    這裡刻意不刪除任何列——極端高溫、暴雨在真實天氣資料裡是有意義的
    訊號（颱風、熱浪),不是雜訊,刪掉會讓分析失真。清理報告只負責「讓你
    看見」有哪些離群值,決定怎麼處理是下游分析（例如 stage4 特徵工程)的
    責任,不在這裡先斬後奏。
    """
    report = {
        "missing_values": missing_value_report(df),
        "dtypes": dtype_check(df),
        "row_count": len(df),
        "outlier_counts": {
            col: len(detect_outliers_iqr(df, col))
            for col in ["temperature_2m_max", "precipitation_sum", "windspeed_10m_max"]
        },
    }
    return df, report


def add_weather_flags(df: pd.DataFrame) -> pd.DataFrame:
    """加上 is_rainy / is_hot 布林欄位,門檻與全課程共用定義一致。"""
    df = df.copy()
    df["is_rainy"] = df["precipitation_sum"] >= RAINY_PRECIP_MM
    df["is_hot"] = df["temperature_2m_max"] >= HOT_TEMP_C
    return df


# ---------------------------------------------------------------------------
# 彙整
# ---------------------------------------------------------------------------


def monthly_climatology(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """依 city x month 算多年平均（氣候學上的「常態」概念：同一個月份、
    不同年份的平均值,用來看季節性循環)。回傳 index=month、columns=city
    的寬格式表,方便直接畫多條線。
    """
    grouped = df.groupby(["month", "city"])[column].mean().reset_index()
    return grouped.pivot(index="month", columns="city", values=column)


def yearly_trend(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """依 city x year 算年平均,回傳寬格式表（index=year, columns=city）。"""
    grouped = df.groupby(["year", "city"])[column].mean().reset_index()
    return grouped.pivot(index="year", columns="city", values=column)


def extreme_events_summary(
    df: pd.DataFrame, temp_threshold: float = HOT_TEMP_C, precip_threshold: float = 50.0
) -> pd.DataFrame:
    """回傳每個城市的極端高溫天數（>= temp_threshold）與暴雨天數
    （precipitation_sum >= precip_threshold mm）統計。
    """
    rows = []
    for city, g in df.groupby("city"):
        rows.append(
            {
                "city": city,
                "extreme_hot_days": int((g["temperature_2m_max"] >= temp_threshold).sum()),
                "heavy_rain_days": int((g["precipitation_sum"] >= precip_threshold).sum()),
                "total_days": len(g),
            }
        )
    return pd.DataFrame(rows).set_index("city")


def top_extreme_events(df: pd.DataFrame, column: str, n: int = 5, ascending: bool = False) -> pd.DataFrame:
    """列出某欄位前 n 名極值事件（含 date/city），供 notebook 逐筆點名討論。"""
    cols = [c for c in ["date", "city", column] if c in df.columns]
    return df.sort_values(column, ascending=ascending)[cols].head(n)


def correlation_matrix(df: pd.DataFrame, columns: list[str] = NUMERIC_COLUMNS) -> pd.DataFrame:
    """數值欄位的皮爾森相關係數矩陣（合併三城市資料,不分城市計算)。"""
    return df[columns].corr()


# ---------------------------------------------------------------------------
# 畫圖：全部真實資料，中文標題用 common/fonts.py 設定字型。
# 每個函式回傳 matplotlib Figure，notebook 負責 savefig 或直接顯示。
# ---------------------------------------------------------------------------

CITY_COLORS = {"taipei": "#4472c4", "taichung": "#c78d1e", "kaohsiung": "#c0392b"}
MONTH_LABELS = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"]


def _new_figure(figsize=(8, 5)):
    import matplotlib.pyplot as plt

    from common.fonts import setup_chinese_font

    setup_chinese_font()
    fig, ax = plt.subplots(figsize=figsize)
    return fig, ax


def plot_temperature_annual_cycle(df: pd.DataFrame):
    """圖一：三城市溫度年週期（月平均溫，看季節循環）。"""
    climatology = monthly_climatology(df, "temperature_2m_mean")
    fig, ax = _new_figure()
    for city in CITIES:
        ax.plot(
            climatology.index,
            climatology[city],
            marker="o",
            label=CITY_NAME_ZH[city],
            color=CITY_COLORS[city],
        )
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(MONTH_LABELS)
    ax.set_ylabel("月平均溫（°C）")
    ax.set_title("三城市溫度年週期（2015-2025 月平均）")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig


def plot_high_temp_comparison(df: pd.DataFrame):
    """圖二：三城市高溫比較（每日最高溫分布，箱型圖）。"""
    fig, ax = _new_figure()
    data = [df[df["city"] == city]["temperature_2m_max"] for city in CITIES]
    bp = ax.boxplot(data, tick_labels=[CITY_NAME_ZH[c] for c in CITIES], patch_artist=True)
    for patch, city in zip(bp["boxes"], CITIES):
        patch.set_facecolor(CITY_COLORS[city])
        patch.set_alpha(0.5)
    ax.set_ylabel("每日最高溫（°C）")
    ax.set_title("三城市每日最高溫分布比較（2015-2025，全部 4018 天/城市）")
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    return fig


def plot_rainfall_seasonal_distribution(df: pd.DataFrame):
    """圖三：降雨季節分布（月平均降雨量，分組長條圖）。"""
    climatology = monthly_climatology(df, "precipitation_sum")
    fig, ax = _new_figure()
    x = np.arange(1, 13)
    width = 0.25
    for i, city in enumerate(CITIES):
        ax.bar(x + (i - 1) * width, climatology[city], width, label=CITY_NAME_ZH[city], color=CITY_COLORS[city])
    ax.set_xticks(x)
    ax.set_xticklabels(MONTH_LABELS)
    ax.set_ylabel("月平均日降雨量（mm）")
    ax.set_title("三城市降雨季節分布（2015-2025 月平均）")
    ax.legend()
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    return fig


def plot_extreme_events(df: pd.DataFrame):
    """圖四：極端高溫/暴雨事件盤點（分組長條圖，count）。"""
    summary = extreme_events_summary(df)
    fig, ax = _new_figure()
    x = np.arange(len(CITIES))
    width = 0.35
    hot = [summary.loc[c, "extreme_hot_days"] for c in CITIES]
    rain = [summary.loc[c, "heavy_rain_days"] for c in CITIES]
    ax.bar(x - width / 2, hot, width, label=f"極端高溫天數（≥{HOT_TEMP_C}°C）", color="#c0392b")
    ax.bar(x + width / 2, rain, width, label="暴雨天數（≥50mm）", color="#4472c4")
    ax.set_xticks(x)
    ax.set_xticklabels([CITY_NAME_ZH[c] for c in CITIES])
    ax.set_ylabel("天數（11 年累計）")
    ax.set_title("極端高溫/暴雨事件盤點（2015-2025 累計天數）")
    ax.legend()
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    return fig


def plot_annual_trend(df: pd.DataFrame):
    """圖五：年際趨勢（年平均溫，看是否有逐年變化）。"""
    trend = yearly_trend(df, "temperature_2m_mean")
    fig, ax = _new_figure()
    for city in CITIES:
        ax.plot(trend.index, trend[city], marker="o", label=CITY_NAME_ZH[city], color=CITY_COLORS[city])
    ax.set_xlabel("年")
    ax.set_ylabel("年平均溫（°C）")
    ax.set_title("三城市年平均溫年際趨勢（2015-2025）")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig


def plot_correlation_matrix(df: pd.DataFrame):
    """圖六：變數相關矩陣（皮爾森相關係數熱圖，合併三城市資料）。"""
    corr = correlation_matrix(df)
    fig, ax = _new_figure(figsize=(8, 7))
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=90)
    ax.set_yticks(range(len(corr.columns)))
    ax.set_yticklabels(corr.columns)
    for i in range(len(corr.columns)):
        for j in range(len(corr.columns)):
            ax.text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center", fontsize=7)
    fig.colorbar(im, ax=ax, shrink=0.8)
    ax.set_title("天氣變數相關矩陣（皮爾森相關係數，三城市合併）")
    fig.tight_layout()
    return fig
