"""stage4 特徵工程：lag 1/2/3、rolling 7/30 均值、月份、城市 one-hot。

兩個預測目標都是「用第 t 天已知的資訊，預測第 t+1 天（明天）」：
- `target_rain_tomorrow`：明天是否下雨（`precipitation_sum >= RAIN_THRESHOLD_MM`）。
- `target_temp_max_tomorrow`：明天的最高溫（`temperature_2m_max`）。

雨天門檻 `RAIN_THRESHOLD_MM = 1.0` 跟 `stage2_eda`/
`scripts/generate_synthetic.py` 用同一個定義，全課程統一。

**為什麼命名是 lag_1/2/3 而不是 lag_0/1/2**：這裡的「lag_k」定義成
「目標日期（明天）往回數第 k 天」，所以 `lag_1_temp_max` 就是「今天」的
溫度（明天往回數 1 天），`lag_2_temp_max` 是「昨天」，`lag_3_temp_max`
是「前天」。這個命名法刻意讓 `lag_1_*` 直接等於 persistence 基準線
（「明天=今天」）用到的那個值——模型要贏過基準線，換句話說就是要在
「只用 lag_1 這一個特徵」的基礎上，證明加其他特徵有沒有幫助。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stage2_eda.weather_eda import CITIES, load_all_cities  # noqa: E402

RAIN_THRESHOLD_MM = 1.0  # 與 stage2_eda.weather_eda.RAINY_PRECIP_MM 一致

LAG_DAYS = [1, 2, 3]
ROLLING_WINDOWS = [7, 30]

FEATURE_COLUMNS = (
    [f"lag_{k}_temp_max" for k in LAG_DAYS]
    + [f"lag_{k}_precip" for k in LAG_DAYS]
    + [f"rolling_{w}_temp_max" for w in ROLLING_WINDOWS]
    + [f"rolling_{w}_precip" for w in ROLLING_WINDOWS]
    + ["month"]
    + [f"city_{c}" for c in CITIES]
)


def build_features(df: pd.DataFrame | None = None, require_target: bool = True) -> pd.DataFrame:
    """輸入三城市合併的原始天氣資料（沒有的話自動 load_all_cities()），
    回傳加上全部特徵欄與兩個目標欄的 DataFrame。

    一定會丟掉：資料不足以算出 rolling_30（每個城市開頭 29 天）的列。

    `require_target=True`（訓練用預設值）另外丟掉沒有「明天」可以當目標的
    列（每個城市最後一天）。`predict.py` 做真實推論時會傳
    `require_target=False`——你想預測「最新一天的明天」時，那一天本來就
    不該有目標值（明天還沒發生），不能因為缺目標就把它丟掉。

    回傳的 DataFrame 保留 `date`/`city` 兩欄方便除錯與時間切分，
    實際餵給模型時只取 `FEATURE_COLUMNS`。
    """
    if df is None:
        df = load_all_cities()

    df = df.sort_values(["city", "date"]).reset_index(drop=True)
    parts = []
    for city, g in df.groupby("city", sort=False):
        g = g.sort_values("date").reset_index(drop=True)

        for k in LAG_DAYS:
            g[f"lag_{k}_temp_max"] = g["temperature_2m_max"].shift(k - 1)
            g[f"lag_{k}_precip"] = g["precipitation_sum"].shift(k - 1)

        for w in ROLLING_WINDOWS:
            g[f"rolling_{w}_temp_max"] = g["temperature_2m_max"].rolling(window=w, min_periods=w).mean()
            g[f"rolling_{w}_precip"] = g["precipitation_sum"].rolling(window=w, min_periods=w).mean()

        # 注意：g["precipitation_sum"].shift(-1) 在每個城市最後一列會是 NaN
        # （沒有「明天」）。float Series 的 `>= ` 比較對 NaN 一律回傳 False
        # （不是 NaN！），如果直接 `.astype("Int64")`，最後一列會被錯誤地
        # 標成「明天不會下雨」，而不是「不知道」——這裡曾經真的踩過這個坑
        # （手動測試 predict.py 對資料集最後一天推論時才發現，見
        # report.md「踩坑紀錄」)，用 `.mask()` 明確把缺值位置轉回 NaN
        # 再轉型,不能只靠比較運算子本身。
        next_day_precip = g["precipitation_sum"].shift(-1)
        g["target_rain_tomorrow"] = (next_day_precip >= RAIN_THRESHOLD_MM).mask(next_day_precip.isna()).astype("Int64")
        g["target_temp_max_tomorrow"] = g["temperature_2m_max"].shift(-1)

        parts.append(g)

    result = pd.concat(parts, ignore_index=True)

    for c in CITIES:
        result[f"city_{c}"] = (result["city"] == c).astype(int)

    required = list(FEATURE_COLUMNS)
    if require_target:
        required += ["target_rain_tomorrow", "target_temp_max_tomorrow"]
    result = result.dropna(subset=required).reset_index(drop=True)
    # require_target=False 時最後一列可能沒有目標（NaN），用可空的 Int64
    # 型別裝著；require_target=True 時已經確定沒有 NaN，轉成一般 int 給
    # sklearn 用起來更直接。
    result["target_rain_tomorrow"] = result["target_rain_tomorrow"].astype(
        int if require_target else "Int64"
    )
    return result


def split_train_test(df: pd.DataFrame, train_end: str = "2023-12-31") -> tuple[pd.DataFrame, pd.DataFrame]:
    """時間序列切分：<=train_end 當訓練集，其餘（train_end 之後）當測試集。

    **為什麼不能隨機切分（train_test_split(shuffle=True)）**：天氣資料
    有強烈的時間自相關——「今天」的天氣跟「明天」的天氣高度相關（這正是
    我們用 lag 特徵的原因）。如果隨機切分，測試集裡混進訓練集「隔壁那
    一天」的資料，模型等於在測試時偷看到高度相關的鄰近資訊，評估出來的
    分數會虛高，沒有反映模型在「真正未見過的未來」上的表現。時間切分
    （訓練集永遠在測試集之前）才是誠實模擬「用過去預測未來」這個真實
    使用情境。
    """
    train_end_ts = pd.Timestamp(train_end)
    train_df = df[df["date"] <= train_end_ts].reset_index(drop=True)
    test_df = df[df["date"] > train_end_ts].reset_index(drop=True)
    return train_df, test_df


# ---------------------------------------------------------------------------
# 基準線：模型一定要贏過這些，才算「有學到東西」
# ---------------------------------------------------------------------------


def persistence_rain_baseline(test_df: pd.DataFrame) -> pd.Series:
    """persistence：預測「明天下雨」= 今天有沒有下雨（lag_1_precip 就是今天的
    降雨量，這裡直接沿用 lag_1 特徵，不用重新查一次原始資料）。
    """
    return (test_df["lag_1_precip"] >= RAIN_THRESHOLD_MM).astype(int)


def climatology_rain_baseline(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
    """氣候頻率基準線：用訓練集裡「這個城市 x 這個月份」的歷史下雨機率，
    當作測試集每一列的預測機率（label 用 0.5 門檻二值化）。
    """
    clima = train_df.groupby(["city", "month"])["target_rain_tomorrow"].mean()
    global_rate = train_df["target_rain_tomorrow"].mean()
    probs = test_df.apply(lambda row: clima.get((row["city"], row["month"]), global_rate), axis=1)
    return probs


def persistence_temp_baseline(test_df: pd.DataFrame) -> pd.Series:
    """persistence：預測「明天最高溫」= 今天的最高溫（lag_1_temp_max）。"""
    return test_df["lag_1_temp_max"]


def monthly_mean_temp_baseline(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
    """月均值基準線：用訓練集裡「這個城市 x 這個月份」的歷史平均最高溫，
    當作測試集每一列的預測值。
    """
    monthly_mean = train_df.groupby(["city", "month"])["temperature_2m_max"].mean()
    global_mean = train_df["temperature_2m_max"].mean()
    return test_df.apply(lambda row: monthly_mean.get((row["city"], row["month"]), global_mean), axis=1)
