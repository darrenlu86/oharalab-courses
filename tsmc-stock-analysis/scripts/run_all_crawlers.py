"""
scripts/run_all_crawlers.py — 依序執行三支爬蟲的排程入口。

做什麼：
    依序呼叫股價、新聞、供應鏈三支爬蟲的主要函式（crawl / crawl_news / run），
    任一支執行途中拋出例外，記一筆 ERROR log 並繼續執行下一支，不會因為
    其中一支失敗（例如新聞網站當天改版、TWSE API 暫時打不通）就讓整批
    排程中斷；三支都跑完後印出一份總結（每支成功／失敗、寫入或新增筆數）。

為什麼這樣設計：
    這是給排程系統（cron／Windows 工作排程器／未來的雲端排程）用的單一
    入口——排程只需要設定「定時執行這一支腳本」，不需要知道底下實際有
    三支爬蟲、也不需要各自設定三條排程規則。「單支失敗不中斷整批」是
    排程腳本的基本要求：見 README.md「定時自動執行爬蟲」一節與規格書
    §9 品質底線「網路錯誤不可讓整支爬蟲 crash」的精神——這裡把同一個
    原則從「單支爬蟲內的單筆資料」再往上套用到「一次排程內的單支爬蟲」。

使用方式：
    venv/bin/python scripts/run_all_crawlers.py
    venv/bin/python scripts/run_all_crawlers.py --months 3 --news-limit 20

注意（初學者常見誤解）：
    這支腳本本身不重新實作任何抓取或清理邏輯，只是「依序呼叫」三支爬蟲
    各自已經寫好的主要函式；真正的抓取細節請直接看
    crawlers/stock_crawler.py、crawlers/news_crawler.py、
    crawlers/supply_chain_crawler.py。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 讓本腳本不論從專案根目錄或其他工作目錄執行，都能正確 import 到
# 專案根目錄的 config / db / crawlers 套件（比照 scripts/init_db.py 的作法）。
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.common import setup_logging  # noqa: E402
from crawlers.news_crawler import crawl_news  # noqa: E402
from crawlers.stock_crawler import crawl as crawl_stock_prices  # noqa: E402
from crawlers.supply_chain_crawler import run as run_supply_chain  # noqa: E402

logger = setup_logging("run_all_crawlers")

DEFAULT_MONTHS = 3
DEFAULT_NEWS_LIMIT = 20


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="依序執行股價／新聞／供應鏈三支爬蟲，供排程系統呼叫。"
    )
    parser.add_argument(
        "--months",
        type=int,
        default=DEFAULT_MONTHS,
        help=(
            "傳給股價爬蟲的 --months 參數：無既有資料（第一次執行）時，"
            f"要往前 backfill 幾個月（預設 {DEFAULT_MONTHS}）；已有資料時"
            "會改用 checkpoint 接續抓取，不受此參數影響。"
        ),
    )
    parser.add_argument(
        "--news-limit",
        type=int,
        default=DEFAULT_NEWS_LIMIT,
        help=f"傳給新聞爬蟲的 --limit 參數：最多擷取幾篇新聞（預設 {DEFAULT_NEWS_LIMIT}）。",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """依序執行三支爬蟲，回傳整體結束碼（0 表示全部成功，1 表示至少一支失敗）。

    做什麼＋為什麼：
        每一支爬蟲都包在自己的 try/except 裡，任何例外只記 log、不重新
        拋出，確保三支都會被嘗試執行到；最後統一印出總結，讓學員（或排程
        系統的通知機制）一眼看出哪支成功、哪支失敗。
    """
    args = parse_args(argv)

    # (顯示名稱, 是否成功, 結果說明) 的清單，供最後印總結用。
    results: list[tuple[str, bool, str]] = []

    logger.info("=== 開始執行股價爬蟲（--months %d）===", args.months)
    try:
        written = crawl_stock_prices(months=args.months)
        results.append(("股價", True, f"寫入(新增/更新) {written} 筆"))
    except Exception as exc:  # noqa: BLE001 — 單支爬蟲失敗不可中斷整批排程
        logger.error("股價爬蟲執行失敗，跳過，繼續下一支：%s", exc, exc_info=True)
        results.append(("股價", False, f"執行失敗：{exc}"))

    logger.info("=== 開始執行新聞爬蟲（--news-limit %d）===", args.news_limit)
    try:
        new_count = crawl_news(limit=args.news_limit)
        results.append(("新聞", True, f"新增 {new_count} 筆（重複 url 不計入）"))
    except Exception as exc:  # noqa: BLE001
        logger.error("新聞爬蟲執行失敗，跳過，繼續下一支：%s", exc, exc_info=True)
        results.append(("新聞", False, f"執行失敗：{exc}"))

    logger.info("=== 開始執行供應鏈爬蟲 ===")
    try:
        run_supply_chain()
        results.append(("供應鏈", True, "完成，詳細筆數見 logs/crawler.log"))
    except Exception as exc:  # noqa: BLE001
        logger.error("供應鏈爬蟲執行失敗：%s", exc, exc_info=True)
        results.append(("供應鏈", False, f"執行失敗：{exc}"))

    logger.info("=== 執行總結 ===")
    failed_count = 0
    for name, ok, detail in results:
        status = "成功" if ok else "失敗"
        if not ok:
            failed_count += 1
        # 注意：不用 print()——setup_logging() 已經同時把這則訊息送到終端機
        # （stdout）與 logs/crawler.log，logger.info() 一行就同時滿足「當下
        # 看得到」與「事後排查看得到」兩個需求，不需要再另外 print 一次
        # （排程執行一律 logging，見 DEVELOPMENT.md）。
        logger.info("%s：%s（%s）", name, status, detail)

    if failed_count:
        logger.warning(
            "本次排程共有 %d/%d 支爬蟲失敗，請查看 logs/crawler.log 排查原因",
            failed_count,
            len(results),
        )
    else:
        logger.info("本次排程三支爬蟲皆執行成功")

    return 1 if failed_count else 0


if __name__ == "__main__":
    sys.exit(main())
