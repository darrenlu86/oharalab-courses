"""載入已訓練的文字情感分類模型，對任意一句話做推論。

用法：
    venv/bin/python -m stage5_ml_unstructured.predict_text --text "今天下雨超級討厭"

執行前請先跑過：
    venv/bin/python -m stage5_ml_unstructured.train_text
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stage5_ml_unstructured.text_features import tokenize  # noqa: E402
from stage5_ml_unstructured.train_text import MODELS_DIR, MODEL_VERSION  # noqa: E402


def load_text_model(models_dir: Path = MODELS_DIR, version: str = MODEL_VERSION) -> dict:
    paths = {
        "vectorizer": models_dir / f"text_vectorizer_{version}.joblib",
        "model": models_dir / f"text_mlp_{version}.joblib",
    }
    missing = [name for name, p in paths.items() if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"找不到模型檔案 {missing}，請先執行：venv/bin/python -m stage5_ml_unstructured.train_text"
        )
    return {name: joblib.load(p) for name, p in paths.items()}


def predict_sentiment(text: str, loaded: dict | None = None) -> dict:
    if loaded is None:
        loaded = load_text_model()
    tokens = tokenize(text)
    X = loaded["vectorizer"].transform([tokens])
    proba = float(loaded["model"].predict_proba(X)[0, 1])
    label = int(proba >= 0.5)
    return {"text": text, "tokens": tokens, "label": label, "positive_proba": proba}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="用已訓練的 MLP 情感分類模型判斷一句話是正面還是負面")
    parser.add_argument("--text", required=True, help="要判斷的一句話（中文）")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = predict_sentiment(args.text)
    except FileNotFoundError as exc:
        print(f"[錯誤] {exc}", file=sys.stderr)
        return 1

    label_zh = "正面" if result["label"] == 1 else "負面"
    print(f"輸入：{result['text']}")
    print(f"斷詞：{result['tokens']}")
    print(f"預測：{label_zh}（正面機率 {result['positive_proba']:.1%}）")
    print(
        "提醒：本模型只在合成語料上訓練過（見 report.md「合成語料的侷限」），"
        "面對真實社群文本的表現無法保證，僅供教學示範。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
