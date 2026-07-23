"""一鍵跑全部五支關卡爬蟲，印出各表 row 數統計（爬前/爬後）。

執行前請先在另一個終端機啟動沙盒站：
    venv/bin/python -m uvicorn sandbox_site.app:app --port 8310

用法：
    venv/bin/python -m stage3_crawler.run_all
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stage3_crawler.crawler import (  # noqa: E402
    crawl_announcements,
    crawl_comments,
    crawl_latest_api,
    crawl_records,
    crawl_stations,
)
from stage3_crawler.crawler.db import get_connection, table_row_counts  # noqa: E402
from stage3_crawler.crawler.http_client import DEFAULT_TIMEOUT, USER_AGENT, check_robots_allowed  # noqa: E402

BASE_URL = "http://127.0.0.1:8310"

CHECK_PATHS = ["/stations", "/records", "/comments", "/announcements", "/api/latest"]


def _check_sandbox_reachable(base_url: str) -> bool:
    try:
        requests.get(base_url + "/", timeout=DEFAULT_TIMEOUT)
        return True
    except requests.RequestException:
        return False


def main() -> int:
    if not _check_sandbox_reachable(BASE_URL):
        print(
            f"[錯誤] 連不到沙盒站 {BASE_URL}。請先在另一個終端機執行：\n"
            "  venv/bin/python -m uvicorn sandbox_site.app:app --port 8310\n"
            "確認啟動訊息出現「Uvicorn running on http://127.0.0.1:8310」後再重跑本腳本。",
            file=sys.stderr,
        )
        return 1

    print(f"沙盒站 {BASE_URL} 連線正常，UA：{USER_AGENT}")
    robots_result = check_robots_allowed(BASE_URL, CHECK_PATHS)
    print(f"robots.txt 檢查結果：{robots_result}")
    if not all(robots_result.values()):
        print("[警告] robots.txt 不允許部分路徑，中止爬取（本課程沙盒站預期全部允許）。")
        return 1

    conn = get_connection()
    before = table_row_counts(conn)
    conn.close()
    print(f"爬取前 row 數：{before}")

    start = time.time()

    station_count = len(crawl_stations.crawl(base_url=BASE_URL))
    print(f"[1/5] stations：{station_count} 筆")

    records_counts = crawl_records.crawl_all_cities(base_url=BASE_URL)
    print(f"[2/5] daily_weather（HTML 翻頁）：{records_counts}")

    comments_count = crawl_comments.crawl(base_url=BASE_URL)
    print(f"[3/5] comments：{comments_count} 筆")

    announcements_count = crawl_announcements.crawl(base_url=BASE_URL)
    print(f"[4/5] announcements：{announcements_count} 則")

    latest_counts = crawl_latest_api.crawl_all_cities(base_url=BASE_URL)
    print(f"[5/5] daily_weather（JSON API，近 30 天）：{latest_counts}")

    elapsed = time.time() - start

    conn = get_connection()
    after = table_row_counts(conn)
    conn.close()
    print(f"爬取後 row 數：{after}")
    print(f"總耗時：{elapsed:.1f} 秒")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
