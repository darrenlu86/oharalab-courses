"""案例 A：天氣留言情感二元分類。jieba 斷詞 → TF-IDF → LogisticRegression
基準 vs MLPClassifier（前饋神經網路）。

用法：
    venv/bin/python -m stage5_ml_unstructured.train_text
"""

from __future__ import annotations

import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stage5_ml_unstructured.text_features import load_labeled_comments  # noqa: E402

MODELS_DIR = Path(__file__).resolve().parent / "models"
FIGURES_DIR = Path(__file__).resolve().parent / "figures"
MODEL_VERSION = "v1"
RANDOM_STATE = 42
TEST_SIZE = 0.2


def count_duplicate_content_rows(df: pd.DataFrame) -> int:
    """回傳整份資料裡「內容跟至少一筆其他資料完全相同」的列數。

    合成語料的模板+雜訊組合空間有限（`scripts/generate_synthetic.py`
    容許同一內容最多重複 3 次），這代表如果直接對整份資料隨機切分訓練/
    測試集，測試集裡有機會出現「內容跟訓練集某一筆一模一樣」的列——
    模型不需要泛化，只要背起來就能答對。**開發過程中第一次先不處理這件事
    直接切分，兩個模型都跑出 accuracy=1.000、0 筆誤判**，追查後才發現
    有 916/2040 筆資料的內容跟別筆重複——這是虛高的分數，不是模型真的
    學到東西。修正做法見 `train_and_evaluate()`：先按內容去重再切分。
    """
    return int(df.duplicated(subset="content", keep=False).sum())


def train_and_evaluate() -> dict:
    df = load_labeled_comments()
    duplicate_row_count = count_duplicate_content_rows(df)

    # 先按內容去重再切分，避免同一句話同時出現在訓練集與測試集
    # （見 count_duplicate_content_rows 的踩坑說明）。
    dedup_df = df.drop_duplicates(subset="content").reset_index(drop=True)

    train_df, test_df = train_test_split(
        dedup_df, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=dedup_df["label"]
    )

    vectorizer = TfidfVectorizer(max_features=3000, ngram_range=(1, 2), min_df=2)
    X_train = vectorizer.fit_transform(train_df["tokens"])
    X_test = vectorizer.transform(test_df["tokens"])
    y_train, y_test = train_df["label"], test_df["label"]

    log_reg = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE)
    log_reg.fit(X_train, y_train)

    mlp = MLPClassifier(
        hidden_layer_sizes=(64,), max_iter=500, random_state=RANDOM_STATE, early_stopping=True
    )
    mlp.fit(X_train, y_train)

    results = {}
    predictions = {}
    for name, model in [("logistic_regression", log_reg), ("mlp_neural_network", mlp)]:
        pred = model.predict(X_test)
        predictions[name] = pred
        results[name] = {
            "accuracy": accuracy_score(y_test, pred),
            "precision": precision_score(y_test, pred, zero_division=0),
            "recall": recall_score(y_test, pred, zero_division=0),
            "f1": f1_score(y_test, pred, zero_division=0),
        }

    # 錯誤案例分析：MLP 的誤判逐筆列出（含機率），供人工檢視。
    mlp_proba = mlp.predict_proba(X_test)[:, 1]
    scored_test = test_df.assign(predicted=predictions["mlp_neural_network"], predicted_proba=mlp_proba)
    misclassified = scored_test[scored_test["predicted"] != scored_test["label"]]

    # 「最接近誤判」的正確案例（預測機率離 0.5 最近）：去重後誤判筆數可能
    # 遠低於 SPEC 要求列出的 5~10 筆討論量，這裡補上模型「猶豫得最厲害」
    # 的正確案例，讓錯誤案例分析仍然有東西可以逐筆討論，不是硬湊數字。
    correct = scored_test[scored_test["predicted"] == scored_test["label"]].copy()
    correct["distance_from_boundary"] = (correct["predicted_proba"] - 0.5).abs()
    closest_calls = correct.sort_values("distance_from_boundary").head(10)

    return {
        "results": results,
        "models": {"logistic_regression": log_reg, "mlp_neural_network": mlp, "vectorizer": vectorizer},
        "y_test": y_test,
        "mlp_pred": predictions["mlp_neural_network"],
        "misclassified": misclassified,
        "closest_calls": closest_calls,
        "duplicate_row_count": duplicate_row_count,
        "raw_row_count": len(df),
        "dedup_row_count": len(dedup_df),
        "train_size": len(train_df),
        "test_size": len(test_df),
        "label_balance": dedup_df["label"].value_counts().to_dict(),
    }


def print_results_table(results: dict) -> None:
    print(f"{'模型':<22}{'accuracy':>10}{'precision':>11}{'recall':>9}{'f1':>8}")
    for name, m in results.items():
        print(f"{name:<22}{m['accuracy']:>10.3f}{m['precision']:>11.3f}{m['recall']:>9.3f}{m['f1']:>8.3f}")


def _print_scored_rows(df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        true_label = "正面" if row["label"] == 1 else "負面"
        pred_label = "正面" if row["predicted"] == 1 else "負面"
        print(
            f"  rating={row['rating']} 實際={true_label} 預測={pred_label} "
            f"(機率={row['predicted_proba']:.2f}) 內容：{row['content']}"
        )


def print_misclassified_examples(result: dict, n: int = 10) -> None:
    misclassified = result["misclassified"]
    print(f"\nMLP 誤判案例（共 {len(misclassified)} 筆，列出前 {min(n, len(misclassified))} 筆）：")
    _print_scored_rows(misclassified.head(n))

    if len(misclassified) < n:
        print(
            f"\n誤判筆數（{len(misclassified)}）低於 SPEC 要求討論的 5~10 筆，"
            "補列模型「猶豫得最厲害」但答對的案例（機率離 0.5 最近），供逐筆討論："
        )
        _print_scored_rows(result["closest_calls"])


def save_figures(result: dict) -> None:
    import matplotlib.pyplot as plt

    from common.fonts import setup_chinese_font

    setup_chinese_font()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    cm = confusion_matrix(result["y_test"], result["mlp_pred"])
    fig, ax = plt.subplots(figsize=(5, 4.5))
    im = ax.imshow(cm, cmap="Greens")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center", fontsize=14)
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["負面", "正面"])
    ax.set_yticklabels(["負面", "正面"])
    ax.set_xlabel("預測")
    ax.set_ylabel("實際")
    ax.set_title("留言情感分類混淆矩陣（MLP，測試集）")
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig01_text_confusion_matrix.png", dpi=100)
    plt.close(fig)


def main() -> int:
    print("載入合成留言語料（rating=3 已排除）...")
    result = train_and_evaluate()
    print(
        f"原始資料：{result['raw_row_count']} 筆，其中 {result['duplicate_row_count']} 筆內容跟"
        f"別筆完全重複；去重後：{result['dedup_row_count']} 筆（訓練/測試切分皆基於去重後資料）"
    )
    print(f"訓練集：{result['train_size']} 筆／測試集：{result['test_size']} 筆")
    print(f"標籤分布（去重後）：{result['label_balance']}（1=正面 rating 4-5，0=負面 rating 1-2）")
    print()
    print_results_table(result["results"])
    print_misclassified_examples(result)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(result["models"]["vectorizer"], MODELS_DIR / f"text_vectorizer_{MODEL_VERSION}.joblib")
    joblib.dump(result["models"]["logistic_regression"], MODELS_DIR / f"text_logistic_regression_{MODEL_VERSION}.joblib")
    joblib.dump(result["models"]["mlp_neural_network"], MODELS_DIR / f"text_mlp_{MODEL_VERSION}.joblib")
    print(f"\n模型已存至 {MODELS_DIR}/（gitignored，本腳本可重新產生）")

    save_figures(result)
    print(f"圖表已存至 {FIGURES_DIR}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
