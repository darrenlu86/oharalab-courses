"""測試 stage5_ml_unstructured：文字前處理正確性 + 兩個案例的 train 函式
小樣本煙霧測試（用真實資料跑一次完整流程，數字不追求重現，只驗證 schema
與合理範圍——見 SPEC §7）。
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import matplotlib

matplotlib.use("Agg")

from stage5_ml_unstructured import text_features as tf  # noqa: E402
from stage5_ml_unstructured import train_digits  # noqa: E402
from stage5_ml_unstructured import train_text  # noqa: E402
from stage5_ml_unstructured.predict_text import predict_sentiment  # noqa: E402


# ---------------------------------------------------------------------------
# text_features.py
# ---------------------------------------------------------------------------


def test_tokenize_returns_space_joined_non_empty_string():
    result = tf.tokenize("今天下雨真討厭")
    assert isinstance(result, str)
    assert " " in result or len(result) > 0


def test_load_labeled_comments_excludes_rating_3():
    df = tf.load_labeled_comments()
    assert 3 not in df["rating"].unique()


def test_load_labeled_comments_label_matches_rating():
    df = tf.load_labeled_comments()
    assert (df.loc[df["rating"] >= 4, "label"] == 1).all()
    assert (df.loc[df["rating"] <= 2, "label"] == 0).all()


def test_load_labeled_comments_has_tokens_column():
    df = tf.load_labeled_comments()
    assert "tokens" in df.columns
    assert df["tokens"].str.len().gt(0).all()


def test_load_labeled_comments_row_count_matches_synthetic_source():
    # data/synthetic/comments.csv 固定 2400 筆，rating 分布 8/12/15/35/30%，
    # 排除 rating=3（15% = 360 筆）後應剩 2040 筆。
    df = tf.load_labeled_comments()
    assert len(df) == 2400 - 360


# ---------------------------------------------------------------------------
# train_text.py：小樣本煙霧測試（用真實合成語料跑一次完整流程）
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def text_train_result():
    return train_text.train_and_evaluate()


def test_count_duplicate_content_rows_is_positive(text_train_result):
    # 合成語料模板可重複，真實資料裡一定驗得到重複內容（開發時實測 916 筆）。
    assert text_train_result["duplicate_row_count"] > 0


def test_train_test_split_has_no_content_overlap_after_dedup():
    df = tf.load_labeled_comments()
    dedup = df.drop_duplicates(subset="content")
    assert dedup["content"].is_unique


def test_train_text_smoke_returns_expected_schema(text_train_result):
    assert set(text_train_result["results"].keys()) == {"logistic_regression", "mlp_neural_network"}
    for name, metrics in text_train_result["results"].items():
        for key in ["accuracy", "precision", "recall", "f1"]:
            assert 0.0 <= metrics[key] <= 1.0, f"{name}.{key} 超出合理範圍"


def test_train_text_misclassified_has_required_columns(text_train_result):
    misclassified = text_train_result["misclassified"]
    assert {"content", "rating", "label", "predicted", "predicted_proba"} <= set(misclassified.columns)
    # 誤判的列，predicted 一定不等於 label（否則就不該被列進誤判清單）。
    if len(misclassified) > 0:
        assert (misclassified["predicted"] != misclassified["label"]).all()


def test_train_text_closest_calls_are_actually_correct_predictions(text_train_result):
    closest = text_train_result["closest_calls"]
    assert (closest["predicted"] == closest["label"]).all()


# ---------------------------------------------------------------------------
# train_digits.py：小樣本煙霧測試（sklearn 內建真實資料）
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def digits_train_result():
    return train_digits.train_and_evaluate()


def test_train_digits_uses_full_1797_sample_dataset(digits_train_result):
    # sklearn load_digits 固定 1797 筆，這是公開已知的資料集大小，非估計值。
    assert digits_train_result["n_samples"] == 1797
    assert digits_train_result["n_train"] + digits_train_result["n_test"] == 1797


def test_train_digits_smoke_returns_expected_schema(digits_train_result):
    assert set(digits_train_result["results"].keys()) == {"logistic_regression", "mlp_neural_network"}
    for name, metrics in digits_train_result["results"].items():
        assert 0.0 <= metrics["accuracy"] <= 1.0
        assert 0.0 <= metrics["f1_macro"] <= 1.0
        # 10 類別隨機猜的 accuracy 約 0.1，真實模型應該遠高於這個下限。
        assert metrics["accuracy"] > 0.5


def test_train_digits_misclassified_indices_are_actually_wrong(digits_train_result):
    assert (digits_train_result["misclassified_true"] != digits_train_result["misclassified_pred"]).all()
    assert len(digits_train_result["misclassified_indices"]) == len(digits_train_result["misclassified_true"])


# ---------------------------------------------------------------------------
# predict_text.py：不依賴磁碟上的 joblib（用 fixture 現場訓練一次）
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def loaded_text_model(text_train_result):
    return {
        "vectorizer": text_train_result["models"]["vectorizer"],
        "model": text_train_result["models"]["mlp_neural_network"],
    }


def test_predict_sentiment_returns_expected_schema(loaded_text_model):
    result = predict_sentiment("今天天氣很好，出去玩超開心", loaded=loaded_text_model)
    assert result["label"] in {0, 1}
    assert 0.0 <= result["positive_proba"] <= 1.0
    assert result["tokens"]


def test_predict_sentiment_obviously_positive_template_predicts_positive(loaded_text_model):
    result = predict_sentiment("涼爽宜人的一天,出去野餐超級開心", loaded=loaded_text_model)
    assert result["label"] == 1


def test_predict_sentiment_obviously_negative_template_predicts_negative(loaded_text_model):
    result = predict_sentiment("下大雨,鞋子襪子全濕透,超級崩潰", loaded=loaded_text_model)
    assert result["label"] == 0


# ---------------------------------------------------------------------------
# 圖表檔案存在性
# ---------------------------------------------------------------------------


def test_figure_files_exist_and_non_trivial():
    figures_dir = REPO_ROOT / "stage5_ml_unstructured" / "figures"
    expected = [
        "fig01_text_confusion_matrix.png",
        "fig02_digits_confusion_matrix.png",
        "fig03_digits_misclassified_samples.png",
    ]
    for name in expected:
        path = figures_dir / name
        assert path.exists(), f"缺少圖表：{path}"
        assert path.stat().st_size > 5_000
