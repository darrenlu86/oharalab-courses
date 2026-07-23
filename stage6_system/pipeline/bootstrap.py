"""一鍵初始化：資料庫、資料、模型缺什麼就補什麼，讓 stage6_system 可以
在一台全新環境（只 clone 過 repo，沒手動跑過 stage3/4/5）上直接動起來。

用法：
    venv/bin/python -m stage6_system.pipeline.bootstrap

檢查與動作（依序）：
1. `data/weather_course.db` 不存在或 schema 缺失 → 建立（沿用
   `scripts/init_db.py`）。
2. `daily_weather` 表是空的 → 從 `data/raw/*.csv` 直接匯入（不需要沙盒站
   或爬蟲，走 `update_data.py --from-csv` 的邏輯）。
3. `comments` 表是空的 → 從 `data/synthetic/comments.csv` 直接匯入（同樣
   不需要沙盒站或爬蟲，`/sentiment` 頁面才有資料可以展示）。
4. stage4 的兩個模型（降雨分類、高溫回歸）缺任一個 → 呼叫
   `stage4_ml_structured.train` 的訓練邏輯重建。
5. stage5 的文字情感模型缺失 → 呼叫
   `stage5_ml_unstructured.train_text` 的訓練邏輯重建。

每一步都先檢查「是否已經存在」，已經存在就跳過不重做——這是為什麼你可以
放心重複執行這支腳本，不會每次都重新訓練模型或重新匯入資料。
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import joblib  # noqa: E402
import pandas as pd  # noqa: E402

from common.paths import DB_PATH, SYNTHETIC_DIR  # noqa: E402
from stage3_crawler.crawler.db import get_connection, upsert_comment  # noqa: E402
from stage4_ml_structured import train as stage4_train  # noqa: E402
from stage5_ml_unstructured import train_text as stage5_train_text  # noqa: E402
from stage6_system.pipeline.update_data import update_from_csv  # noqa: E402

STAGE4_MODEL_FILES = [
    stage4_train.MODELS_DIR / f"rain_random_forest_{stage4_train.MODEL_VERSION}.joblib",
    stage4_train.MODELS_DIR / f"temp_random_forest_{stage4_train.MODEL_VERSION}.joblib",
]
STAGE5_TEXT_MODEL_FILES = [
    stage5_train_text.MODELS_DIR / f"text_vectorizer_{stage5_train_text.MODEL_VERSION}.joblib",
    stage5_train_text.MODELS_DIR / f"text_mlp_{stage5_train_text.MODEL_VERSION}.joblib",
]


def ensure_database() -> str:
    if DB_PATH.exists():
        return "資料庫已存在，跳過建立"
    get_connection().close()  # get_connection() 內部呼叫 build_database()，會建檔
    return "資料庫不存在，已建立"


def ensure_daily_weather() -> str:
    conn = get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) FROM daily_weather").fetchone()[0]
        if count > 0:
            return f"daily_weather 已有 {count} 列，跳過匯入"
        counts = update_from_csv(conn=conn)
        return f"daily_weather 原本是空的，已從 data/raw/*.csv 匯入：{counts}"
    finally:
        conn.close()


def ensure_comments(synthetic_dir: Path = SYNTHETIC_DIR) -> str:
    conn = get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
        if count > 0:
            return f"comments 已有 {count} 列，跳過匯入"
        df = pd.read_csv(synthetic_dir / "comments.csv")
        crawled_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for _, row in df.iterrows():
            upsert_comment(conn, row["comment_id"], row["city"], row["date"], int(row["rating"]), row["content"], crawled_at)
        return f"comments 原本是空的，已從 data/synthetic/comments.csv 直接匯入 {len(df)} 筆"
    finally:
        conn.close()


def ensure_stage4_models() -> str:
    if all(p.exists() for p in STAGE4_MODEL_FILES):
        return "stage4 模型（降雨分類＋高溫回歸）已存在，跳過訓練"
    df = stage4_train.build_features()
    train_df, test_df = stage4_train.split_train_test(df)
    clf_result = stage4_train.train_classification(train_df, test_df)
    reg_result = stage4_train.train_regression(train_df, test_df)

    stage4_train.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf_result["models"]["random_forest"], STAGE4_MODEL_FILES[0])
    joblib.dump(reg_result["models"]["random_forest"], STAGE4_MODEL_FILES[1])
    return (
        "stage4 模型缺失，已重新訓練："
        f"降雨分類 accuracy={clf_result['results']['random_forest']['accuracy']:.3f}，"
        f"高溫回歸 MAE={reg_result['results']['random_forest']['mae']:.3f}"
    )


def ensure_stage5_text_model() -> str:
    if all(p.exists() for p in STAGE5_TEXT_MODEL_FILES):
        return "stage5 文字情感模型已存在，跳過訓練"
    result = stage5_train_text.train_and_evaluate()
    stage5_train_text.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(result["models"]["vectorizer"], STAGE5_TEXT_MODEL_FILES[0])
    joblib.dump(result["models"]["mlp_neural_network"], STAGE5_TEXT_MODEL_FILES[1])
    return f"stage5 文字情感模型缺失，已重新訓練：accuracy={result['results']['mlp_neural_network']['accuracy']:.3f}"


def bootstrap() -> list[str]:
    steps = [
        ensure_database,
        ensure_daily_weather,
        ensure_comments,
        ensure_stage4_models,
        ensure_stage5_text_model,
    ]
    return [step() for step in steps]


def main() -> int:
    print("stage6_system 一鍵初始化...")
    for message in bootstrap():
        print(f"  - {message}")
    print("初始化完成。啟動儀表板：venv/bin/python -m uvicorn stage6_system.app:app --port 8320")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
