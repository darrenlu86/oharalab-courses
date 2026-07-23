"""關卡：列表→詳情兩層爬取——先爬 /announcements 列表拿到連結，
再逐一爬 /announcements/{ann_id} 詳情頁，寫進 announcements 表。

這是跟前面幾支關卡不同的模式：不是翻頁,而是「先拿到一批連結,再逐一
展開」。真實世界很多爬蟲任務長這樣（例如電商網站：先爬商品列表頁拿到
連結,再逐一進商品詳情頁拿完整資訊)。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from stage3_crawler.crawler.db import get_connection, upsert_announcement  # noqa: E402
from stage3_crawler.crawler.http_client import PoliteSession  # noqa: E402

DEFAULT_BASE_URL = "http://127.0.0.1:8310"

# <small>{ann_id} ｜ 發布日期：{published_at}</small> 的解析樣式。
DETAIL_META_PATTERN = re.compile(r"(?P<ann_id>\S+)\s*｜\s*發布日期：(?P<published_at>.+)")


def parse_announcements_list(html: str) -> list[dict]:
    """從 /announcements 列表頁解析出 [{ann_id, title, url}, ...]。"""
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for li in soup.select("ul.plain-list li"):
        a = li.find("a")
        href = a["href"]
        ann_id = href.rstrip("/").rsplit("/", 1)[-1]
        items.append({"ann_id": ann_id, "title": a.text.strip(), "url": href})
    return items


def parse_announcement_detail(html: str) -> dict:
    """從 /announcements/{ann_id} 詳情頁解析出 {ann_id, title, body, published_at}。"""
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article")
    title = article.find("h1").text.strip()
    meta_text = article.find("small").text.strip()
    match = DETAIL_META_PATTERN.search(meta_text)
    if match is None:
        raise ValueError(f"詳情頁 meta 格式解析失敗：{meta_text!r}")
    body = article.find_all("p")[1].text.strip()
    return {
        "ann_id": match.group("ann_id"),
        "title": title,
        "body": body,
        "published_at": match.group("published_at").strip(),
    }


def crawl(session: PoliteSession | None = None, base_url: str = DEFAULT_BASE_URL, conn=None) -> int:
    own_session = session is None
    if own_session:
        session = PoliteSession(base_url)
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    try:
        list_resp = session.get("/announcements")
        items = parse_announcements_list(list_resp.text)
        for item in items:
            detail_resp = session.get(item["url"])
            detail = parse_announcement_detail(detail_resp.text)
            upsert_announcement(conn, detail["ann_id"], detail["title"], detail["body"], detail["published_at"])
        return len(items)
    finally:
        if own_session:
            session.close()
        if own_conn:
            conn.close()


def main() -> int:
    count = crawl()
    print(f"announcements: {count} 則（列表→詳情兩層爬取完成)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
