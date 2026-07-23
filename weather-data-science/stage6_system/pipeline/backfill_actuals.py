"""回填 `predictions` 表裡還沒有實際值的預測（監測機制的關鍵一步）。

每次 `/predict` 頁面預測時，`predictions` 表會寫入一列（`actual_precip_mm`/
`actual_label` 為 NULL，因為預測當下「明天」還沒發生）。等 `daily_weather`
表真的有了那個 `target_date` 的資料（跑過 `update_data.py` 之後），這支
腳本負責把預測「兌現」——查出實際降雨量與實際標籤，寫回 `predictions`。

用法：
    venv/bin/python -m stage6_system.pipeline.backfill_actuals
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from stage3_crawler.crawler.db import get_connection  # noqa: E402
from stage4_ml_structured.features import RAIN_THRESHOLD_MM  # noqa: E402


def backfill(conn=None) -> int:
    """回填全部「有實際資料可查但還沒回填」的預測列，回傳回填筆數。"""
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    try:
        pending = conn.execute(
            "SELECT id, city, target_date FROM predictions WHERE actual_label IS NULL"
        ).fetchall()

        backfilled = 0
        for pred_id, city, target_date in pending:
            actual = conn.execute(
                "SELECT precipitation_mm FROM daily_weather WHERE city = ? AND date = ?",
                (city, target_date),
            ).fetchone()
            if actual is None or actual[0] is None:
                continue  # 那天的實際資料還沒進資料庫，之後再回填

            actual_precip = actual[0]
            actual_label = int(actual_precip >= RAIN_THRESHOLD_MM)
            conn.execute(
                "UPDATE predictions SET actual_precip_mm = ?, actual_label = ? WHERE id = ?",
                (actual_precip, actual_label, pred_id),
            )
            backfilled += 1
        conn.commit()
        return backfilled
    finally:
        if own_conn:
            conn.close()


def main() -> int:
    count = backfill()
    print(f"回填完成：{count} 筆預測已補上實際值")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
