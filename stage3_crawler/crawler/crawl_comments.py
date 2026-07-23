"""翻頁爬蟲第二例——爬 /comments?page= 民眾留言（合成語料），寫進 comments 表。

跟 crawl_records.py 邏輯結構相同（解析頁面 → 讀總頁數 → 迴圈翻頁），這裡
刻意重複同一套模式，讓你確認「翻頁爬蟲」是一個可以重複套用的方法，
不是 records 頁面獨有的特例。
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from stage3_crawler.crawler.db import get_connection, upsert_comment  # noqa: E402
from stage3_crawler.crawler.http_client import PoliteSession  # noqa: E402

DEFAULT_BASE_URL = "http://127.0.0.1:8310"
PAGE_CAPTION_PATTERN = re.compile(r"第\s*(\d+)\s*頁\s*/\s*共\s*(\d+)\s*頁")


def parse_comments_page(html: str) -> tuple[list[dict], int, int]:
    """回傳（該頁留言 dict 清單, 目前頁碼, 總頁數）。

    留言的 comment_id 就是資料庫 comments 表的 comment_key（沙盒站上的
    唯一識別碼，見 SPEC §3.3 schema 註解）。
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="comments-table")
    caption_match = PAGE_CAPTION_PATTERN.search(table.find("caption").text)
    page, total_pages = int(caption_match.group(1)), int(caption_match.group(2))

    rows = []
    for tr in table.find("tbody").find_all("tr"):
        cells = [td.text.strip() for td in tr.find_all("td")]
        comment_id, city, date, rating, content = cells
        rows.append(
            {
                "comment_key": comment_id,
                "city": city,
                "date": date,
                "rating": int(rating),
                "content": content,
            }
        )
    return rows, page, total_pages


def crawl(
    session: PoliteSession | None = None,
    base_url: str = DEFAULT_BASE_URL,
    conn=None,
    city: str | None = None,
) -> int:
    """爬全部（或指定 city）留言頁面,upsert 進 comments 表,回傳寫入列數。"""
    own_session = session is None
    if own_session:
        session = PoliteSession(base_url)
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    crawled_at = datetime.now().isoformat(timespec="seconds")
    total_rows = 0
    try:
        page = 1
        total_pages = 1
        params_base = {"city": city} if city else {}
        while page <= total_pages:
            params = {**params_base, "page": page}
            resp = session.get("/comments", params=params)
            rows, current_page, total_pages = parse_comments_page(resp.text)
            for row in rows:
                upsert_comment(
                    conn, row["comment_key"], row["city"], row["date"], row["rating"], row["content"], crawled_at
                )
            total_rows += len(rows)
            page += 1
        return total_rows
    finally:
        if own_session:
            session.close()
        if own_conn:
            conn.close()


def main() -> int:
    count = crawl()
    print(f"comments: {count} 列處理完成（INSERT OR IGNORE，重跑不會增加重複列）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
