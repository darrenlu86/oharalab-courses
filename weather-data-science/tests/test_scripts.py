"""測試 scripts/init_db.py（冪等、--reset）與 scripts/generate_synthetic.py（決定性）。

全部在 tmp_path 或函式層操作，不動 repo 裡真正的 data/weather_course.db，
也不覆寫 data/synthetic/*.csv（只呼叫產生函式比對輸出是否一致，不寫檔）。
"""

import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.init_db import DEFAULT_STATIONS, init_db  # noqa: E402
from scripts.generate_synthetic import (  # noqa: E402
    RATING_TARGET_COUNTS,
    generate_announcements,
    generate_comments,
    load_weather_pool,
)


# ---------------------------------------------------------------------------
# scripts/init_db.py：冪等 + --reset
# ---------------------------------------------------------------------------


def _station_count(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0]
    finally:
        conn.close()


def test_init_db_first_run_creates_three_stations(tmp_path):
    db_path = tmp_path / "weather_course.db"
    init_db(db_path=db_path)
    assert db_path.exists()
    assert _station_count(db_path) == len(DEFAULT_STATIONS) == 3


def test_init_db_rerun_without_reset_is_idempotent(tmp_path):
    db_path = tmp_path / "weather_course.db"
    init_db(db_path=db_path)
    assert _station_count(db_path) == 3

    # 跑第二次（沒有 --reset）：不應該報錯，也不應該改動已存在的資料庫。
    init_db(db_path=db_path)
    assert _station_count(db_path) == 3

    # 跑第三次再確認一次，確保不是「剛好」冪等。
    init_db(db_path=db_path)
    assert _station_count(db_path) == 3


def test_init_db_reset_backs_up_and_rebuilds(tmp_path):
    db_path = tmp_path / "weather_course.db"
    init_db(db_path=db_path)

    # 塞一筆假資料，證明 --reset 真的有重建，不是原地不動。
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO stations (city, name_zh, latitude, longitude) VALUES (?, ?, ?, ?)",
        ("bogus", "測試站", 0.0, 0.0),
    )
    conn.commit()
    conn.close()
    assert _station_count(db_path) == 4

    init_db(db_path=db_path, reset=True)

    assert _station_count(db_path) == 3  # 重建後恢復成預設三個測站，假資料消失
    backups = list(tmp_path.glob(f"{db_path.name}.bak-*"))
    assert len(backups) == 1, f"預期恰好一個備份檔，實際：{backups}"


# ---------------------------------------------------------------------------
# scripts/generate_synthetic.py：決定性 + city/date 存在性 + rating 合法值
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def weather_pool():
    return load_weather_pool()


@pytest.fixture(scope="module")
def raw_dates_by_city():
    """從 data/raw/*.csv 直接讀出每個城市實際存在的日期集合，當作比對基準。"""
    import csv

    from common.paths import RAW_DIR

    result = {}
    for city in ["taipei", "taichung", "kaohsiung"]:
        with (RAW_DIR / f"{city}.csv").open(newline="", encoding="utf-8") as f:
            result[city] = {row["date"] for row in csv.DictReader(f)}
    return result


def test_generate_comments_is_deterministic(weather_pool):
    comments_a, counts_a = generate_comments(weather_pool)
    comments_b, counts_b = generate_comments(weather_pool)
    assert comments_a == comments_b
    assert counts_a == counts_b


def test_generate_announcements_is_deterministic():
    ann_a = generate_announcements()
    ann_b = generate_announcements()
    assert ann_a == ann_b


def test_generate_comments_total_and_rating_counts(weather_pool):
    comments, _ = generate_comments(weather_pool)
    assert len(comments) == sum(RATING_TARGET_COUNTS.values()) == 2400

    from collections import Counter

    rating_counts = Counter(c["rating"] for c in comments)
    assert dict(rating_counts) == RATING_TARGET_COUNTS


def test_generate_comments_city_date_exist_in_raw_data(weather_pool, raw_dates_by_city):
    comments, _ = generate_comments(weather_pool)
    for c in comments:
        assert c["city"] in raw_dates_by_city, f"未知城市：{c['city']}"
        assert c["date"] in raw_dates_by_city[c["city"]], (
            f"{c['city']} {c['date']} 不存在於 data/raw，違反 SPEC §3.2"
        )


def test_generate_comments_rating_only_1_to_5(weather_pool):
    comments, _ = generate_comments(weather_pool)
    ratings = {c["rating"] for c in comments}
    assert ratings <= {1, 2, 3, 4, 5}


def test_generate_comments_no_content_repeated_more_than_3_times(weather_pool):
    comments, content_counts = generate_comments(weather_pool)
    assert max(content_counts.values()) <= 3


def test_generate_announcements_count_and_length(weather_pool):
    announcements = generate_announcements()
    assert len(announcements) == 30
    for a in announcements:
        assert 100 <= len(a["body"]) <= 300
