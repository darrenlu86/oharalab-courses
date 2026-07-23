"""案例 B：手寫數字辨識。sklearn `load_digits`（真實 8x8 手寫數字，內建
零下載）→ MLPClassifier，展示錯分樣本圖。

用法：
    venv/bin/python -m stage5_ml_unstructured.train_digits
"""

from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.datasets import load_digits
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MODELS_DIR = Path(__file__).resolve().parent / "models"
FIGURES_DIR = Path(__file__).resolve().parent / "figures"
MODEL_VERSION = "v1"
RANDOM_STATE = 42
TEST_SIZE = 0.2


def train_and_evaluate() -> dict:
    digits = load_digits()
    X, y = digits.data, digits.target
    X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
        X, y, np.arange(len(X)), test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # 簡單基準線：LogisticRegression 直接吃像素值——用來對照「為什麼要用
    # 神經網路」，不是本案例的必要產出，但能讓你看到差距有多大或多小。
    log_reg = LogisticRegression(max_iter=2000, random_state=RANDOM_STATE)
    log_reg.fit(X_train_scaled, y_train)

    mlp = MLPClassifier(hidden_layer_sizes=(100,), max_iter=1000, random_state=RANDOM_STATE, early_stopping=True)
    mlp.fit(X_train_scaled, y_train)

    results = {}
    predictions = {}
    for name, model in [("logistic_regression", log_reg), ("mlp_neural_network", mlp)]:
        pred = model.predict(X_test_scaled)
        predictions[name] = pred
        results[name] = {
            "accuracy": accuracy_score(y_test, pred),
            "f1_macro": f1_score(y_test, pred, average="macro"),
        }

    mlp_pred = predictions["mlp_neural_network"]
    misclassified_mask = mlp_pred != y_test
    misclassified_indices = idx_test[misclassified_mask]

    return {
        "results": results,
        "models": {"scaler": scaler, "logistic_regression": log_reg, "mlp_neural_network": mlp},
        "y_test": y_test,
        "mlp_pred": mlp_pred,
        "images": digits.images,
        "misclassified_indices": misclassified_indices,
        "misclassified_true": y_test[misclassified_mask],
        "misclassified_pred": mlp_pred[misclassified_mask],
        "n_samples": len(X),
        "n_train": len(X_train),
        "n_test": len(X_test),
    }


def print_results_table(results: dict) -> None:
    print(f"{'模型':<22}{'accuracy':>10}{'f1_macro':>10}")
    for name, m in results.items():
        print(f"{name:<22}{m['accuracy']:>10.3f}{m['f1_macro']:>10.3f}")


def save_figures(result: dict) -> None:
    import matplotlib.pyplot as plt

    from common.fonts import setup_chinese_font

    setup_chinese_font()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    # 圖一：混淆矩陣（10x10，數字 0-9）
    cm = confusion_matrix(result["y_test"], result["mlp_pred"])
    fig, ax = plt.subplots(figsize=(6, 5.5))
    im = ax.imshow(cm, cmap="Purples")
    for i in range(10):
        for j in range(10):
            if cm[i, j] > 0:
                ax.text(j, i, str(cm[i, j]), ha="center", va="center", fontsize=8)
    ax.set_xticks(range(10))
    ax.set_yticks(range(10))
    ax.set_xlabel("預測數字")
    ax.set_ylabel("實際數字")
    ax.set_title("手寫數字辨識混淆矩陣（MLP，測試集）")
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig02_digits_confusion_matrix.png", dpi=100)
    plt.close(fig)

    # 圖二：錯分樣本圖（最多顯示 12 張，8x8 灰階圖 + 實際/預測標籤）
    n_show = min(12, len(result["misclassified_indices"]))
    if n_show > 0:
        cols = 4
        rows = (n_show + cols - 1) // cols
        fig, axes = plt.subplots(rows, cols, figsize=(cols * 2, rows * 2.2))
        axes = np.atleast_1d(axes).flatten()
        for i in range(n_show):
            idx = result["misclassified_indices"][i]
            ax = axes[i]
            ax.imshow(result["images"][idx], cmap="gray_r")
            ax.set_title(
                f"實際:{result['misclassified_true'][i]} 預測:{result['misclassified_pred'][i]}", fontsize=9
            )
            ax.axis("off")
        for i in range(n_show, len(axes)):
            axes[i].axis("off")
        fig.suptitle(f"手寫數字錯分樣本（共 {len(result['misclassified_indices'])} 筆，顯示前 {n_show} 筆）")
        fig.tight_layout()
        fig.savefig(FIGURES_DIR / "fig03_digits_misclassified_samples.png", dpi=100)
        plt.close(fig)


def main() -> int:
    print("載入 sklearn load_digits（真實 8x8 手寫數字，內建無需下載）...")
    result = train_and_evaluate()
    print(f"總樣本數：{result['n_samples']}　訓練：{result['n_train']}　測試：{result['n_test']}")
    print()
    print_results_table(result["results"])
    print(f"\nMLP 誤判樣本數：{len(result['misclassified_indices'])} / {result['n_test']}")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(result["models"]["scaler"], MODELS_DIR / f"digits_scaler_{MODEL_VERSION}.joblib")
    joblib.dump(result["models"]["mlp_neural_network"], MODELS_DIR / f"digits_mlp_{MODEL_VERSION}.joblib")
    print(f"模型已存至 {MODELS_DIR}/（gitignored，本腳本可重新產生）")

    save_figures(result)
    print(f"圖表已存至 {FIGURES_DIR}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
