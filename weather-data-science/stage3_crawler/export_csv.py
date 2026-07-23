"""把 SQLite 四張資料表（stations/daily_weather/comments/announcements）
匯出成 CSV，落地在 stage3_crawler/output/（gitignored，README 示範用）。

用法：
    venv/bin/python -m stage3_crawler.export_csv
"""

from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.paths import DB_PATH  # noqa: E402

OUTPUT_DIR = Path(__file__).resolve().parent / "output"

TABLES = ["stations", "daily_weather", "comments", "announcements"]


def export_table(conn: sqlite3.Connection, table: str, out_dir: Path) -> int:
    cursor = conn.execute(f"SELECT * FROM {table}")
    columns = [d[0] for d in cursor.description]
    rows = cursor.fetchall()

    out_path = out_dir / f"{table}.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)
    return len(rows)


def export_all(db_path: Path = DB_PATH, out_dir: Path = OUTPUT_DIR) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        return {table: export_table(conn, table, out_dir) for table in TABLES}
    finally:
        conn.close()


def main() -> int:
    if not DB_PATH.exists():
        print(f"[錯誤] 找不到資料庫 {DB_PATH}。請先跑 stage3_crawler/run_all.py 或 scripts/init_db.py。", file=sys.stderr)
        return 1
    counts = export_all()
    for table, count in counts.items():
        print(f"{table}.csv：{count} 列 → {OUTPUT_DIR / f'{table}.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
