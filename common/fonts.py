"""matplotlib 中文字型設定。

matplotlib 預設字型不含中文字形，直接畫圖標題會變成方框。
這裡依序嘗試幾個常見中文字型，用 font_manager 實際查詢系統上
有沒有安裝，找到第一個存在的就設為 matplotlib 預設字型；
如果候選清單裡一個都找不到，印警告但不中斷程式（圖還是畫得出來，
只是中文字會變方框），讓學員知道要自己裝字型。
"""

import warnings

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

# 依序嘗試的候選字型：macOS 內建（PingFang TC / Heiti TC / Arial Unicode MS）
# 優先，其次是 Windows 常見的 Microsoft JhengHei，最後是 Linux 常見的
# Noto Sans CJK TC，盡量涵蓋學員可能用的作業系統。
CANDIDATE_FONTS = [
    "PingFang TC",
    "Heiti TC",
    "Arial Unicode MS",
    "Microsoft JhengHei",
    "Noto Sans CJK TC",
]


def setup_chinese_font():
    """依序嘗試候選中文字型，設定 matplotlib 的預設顯示字型。

    回傳實際選用的字型名稱（str）；若候選清單全部找不到，
    印出警告並回傳 None。
    """
    available_names = {font.name for font in fm.fontManager.ttflist}

    for candidate in CANDIDATE_FONTS:
        if candidate in available_names:
            current = plt.rcParams.get("font.sans-serif", [])
            plt.rcParams["font.sans-serif"] = [candidate] + list(current)
            # 中文字型底下，負號預設會被畫成方框，這裡關掉 unicode minus
            # 讓 matplotlib 改用一般減號字元。
            plt.rcParams["axes.unicode_minus"] = False
            return candidate

    warnings.warn(
        "找不到任何候選中文字型（"
        + "、".join(CANDIDATE_FONTS)
        + "），圖表中的中文字可能會顯示為方框。"
        "請安裝其中一種字型後再重新執行。"
    )
    return None
