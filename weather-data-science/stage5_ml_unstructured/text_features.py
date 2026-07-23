"""案例 A 的文字前處理：中文斷詞（jieba）+ 標籤定義 + 資料載入。

非結構化資料（一段中文文字）要餵給 sklearn 的分類器之前，必須先變成
固定長度的數值向量——這支模組負責「斷詞」這一步，向量化（TF-IDF）留在
`train_text.py` 裡用 `TfidfVectorizer` 做，因為向量化需要在訓練集上
`fit`、測試集上只 `transform`（避免資訊從測試集洩漏進詞彙表)，這個
fit/transform 的分際留在訓練腳本裡管理比較清楚。
"""

from __future__ import annotations

import sys
from pathlib import Path

import jieba
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.paths import SYNTHETIC_DIR  # noqa: E402

POSITIVE_RATINGS = {4, 5}
NEGATIVE_RATINGS = {1, 2}
# rating=3（中性）刻意排除，不參與二元分類——3 分的留言語氣通常模稜兩可
# （「普通」「還好」），硬塞進正面或負面都會製造模糊標籤，破壞訓練訊號。
EXCLUDED_RATINGS = {3}


def tokenize(text: str) -> str:
    """用 jieba 斷詞，回傳空格分隔的詞彙字串（給 TfidfVectorizer 當輸入)。

    這裡刻意不特別處理標點符號的斷詞結果（jieba 對逗號、驚嘆號等標點也會
    切出來當作獨立 token）——標點在天氣留言裡其實帶有情緒訊號（例如驚嘆號
    出現頻率跟正面情緒可能有關），直接濾掉可能丟失有用資訊，交給
    TF-IDF 的詞頻統計自己決定要不要重視它。
    """
    return " ".join(jieba.cut(text))


def load_labeled_comments(synthetic_dir: Path = SYNTHETIC_DIR) -> pd.DataFrame:
    """讀 comments.csv，排除 rating=3，加上二元標籤欄 `label`
    （1=正面 rating 4-5，0=負面 rating 1-2）與斷詞後的 `tokens` 欄。
    """
    df = pd.read_csv(synthetic_dir / "comments.csv")
    df = df[df["rating"].isin(POSITIVE_RATINGS | NEGATIVE_RATINGS)].reset_index(drop=True)
    df["label"] = df["rating"].isin(POSITIVE_RATINGS).astype(int)
    df["tokens"] = df["content"].apply(tokenize)
    return df
