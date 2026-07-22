"""
crawlers/supply_chain_crawler.py — 台積電（2330）上下游供應鏈爬蟲。

做什麼：
    抓取「證券櫃檯買賣中心產業價值鏈資訊平台」半導體產業鏈頁面，解析出
    上游／中游／下游各環節（segment，如「IC 設計」「化學品」「IC 封裝測試」）
    底下列出的公司（名稱、股票代號），寫入 supply_chain_companies 資料表，
    以台積電（2330）作為 anchor_symbol（規格書 §5c）。

為什麼這樣設計（取捨教學點）：
    這個頁面是官方平台直接輸出的 server-rendered HTML（用瀏覽器「檢視原始碼」
    就看得到完整內容，不需要等 JavaScript 執行才有資料），所以只要用
    requests 把 HTML 抓下來、交給 BeautifulSoup 解析就夠了，不必像新聞爬蟲
    那樣動用整套 Playwright 瀏覽器——多開一個瀏覽器程序是有成本的（啟動慢、
    吃記憶體），能用簡單工具解決的事就不要用複雜工具。

來源：
    https://ic.tpex.org.tw/introduce.php?ic=D000（半導體產業鏈）
    已實測：HTTP 200、robots.txt 不存在（無限制）、伺服器直出約 280~300KB
    HTML，內含「上游／中游／下游」三大區塊，共 12 個細分環節（segment），
    合計約 600 多筆公司資料。實測也發現台積電自己（2330）出現在「中游／
    IC・晶圓製造」這個 segment 底下——這是頁面真實的分類方式，不是本檔案
    刻意加進去的，維持原樣寫入資料庫（如果之後不想讓 anchor 公司出現在
    自己的供應鏈清單裡，應該是 Dashboard 顯示層的過濾邏輯，不該在爬蟲
    這一層動手腳篡改原始資料）。

注意（Python 3.13 的一個環境陷阱，值得學員認識）：
    開發時實測發現，這個網站的憑證鏈（老牌憑證機構 TWCA 簽發）沒有帶新版
    規範建議的 Subject Key Identifier 擴充欄位——這在憑證界並不罕見（很多
    2010 年前簽發的根憑證都沒有這個欄位），瀏覽器與 curl 都不會因此拒絕
    連線，但 Python 3.13 起 ssl 模組的預設驗證行為變得比業界標準更嚴格，
    會直接把這類連線判定失敗（SSLCertVerificationError: Missing Subject
    Key Identifier）。這不是這個網站不安全，純粹是新版 Python「比瀏覽器
    龜毛」的相容性問題。本檔案的因應方式：先照規格書用 crawlers.common
    的標準 requests 流程（含 robots 檢查、rate limit、重試）抓取；如果
    在某個環境（例如這種舊憑證鏈站台 + 新版 Python）該流程重試多次仍失敗，
    才退而求其次呼叫系統內建的 curl 指令備援（curl 一樣會完整驗證憑證鏈
    與主機名稱，沒有加 `-k`/`--insecure`，不是關掉安全檢查，只是它沒有
    Python 3.13 新增的那條更嚴規則），並把原因記進 log，方便之後環境
    升級（例如 requests/urllib3/certifi 版本更新）後回頭確認這個備援
    是否還需要保留。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

# 讓本檔案不論用 `python -m crawlers.supply_chain_crawler`（建議方式，會自動
# 把目前工作目錄加進 sys.path）還是直接 `python crawlers/supply_chain_crawler.py`
# 執行，都能正確 import 到專案根目錄的 config / db 套件（比照
# stock_crawler.py / news_crawler.py 的作法）。
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawlers import common  # noqa: E402
from db.factory import get_repository  # noqa: E402

# 目標頁面與 anchor 股票代號（依規格書 §5c 固定）。
TPEX_URL = "https://ic.tpex.org.tw/introduce.php?ic=D000"
ANCHOR_SYMBOL = "2330"

# 頁面上「上游/中游/下游」三個區塊標題，對應資料庫 relation 欄位用的英文代碼。
# 用 dict 而不是 if/elif 判斷：資料驅動勝過硬編邏輯，之後要支援其他產業鏈
# 頁面（一樣是「上游/中游/下游」的分類方式）完全不用改這段程式碼。
RELATION_LABELS = {
    "上游": "upstream",
    "中游": "midstream",
    "下游": "downstream",
}

logger = common.setup_logging(__name__)


# ---------------------------------------------------------------------
# 抓取（I/O，含備援機制）
# ---------------------------------------------------------------------
def _fetch_via_curl(url: str, user_agent: str, timeout: int = 20) -> str | None:
    """備援抓取：呼叫系統內建的 curl 指令。

    做什麼＋為什麼：見本檔案最上方模組 docstring 的「注意」一節。只有在
    requests（common.polite_get）走完整套重試流程仍失敗時才會用到，
    且只在本檔案內部使用，不影響 common.py 提供給其他爬蟲的標準流程。

    注意：curl 預設一樣會驗證憑證鏈與主機名稱，這裡沒有加
    `-k`/`--insecure`，刻意保留真正的安全檢查——這不是關掉驗證，只是換
    一個沒有踩到 Python 3.13 新規則的用戶端。
    """
    try:
        result = subprocess.run(
            ["curl", "-s", "-A", user_agent, "--max-time", str(timeout), url],
            capture_output=True,
            timeout=timeout + 5,
            check=True,
        )
        return result.stdout.decode("utf-8", errors="replace")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        logger.error("curl 備援抓取也失敗，放棄：%s（錯誤：%s）", url, exc)
        return None


def fetch_supply_chain_page(url: str = TPEX_URL) -> str | None:
    """抓取產業價值鏈頁面 HTML；失敗時記 log 並回傳 None（呼叫端需自行檢查）。

    流程：先檢查 robots.txt（禁止就直接跳過，不重試、不備援）→ 用
    common.polite_get 走標準的 rate limit／重試流程 → 失敗才退而求其次
    用 curl 備援。
    """
    if not common.check_robots_allowed(url, common.USER_AGENT):
        logger.error("robots.txt 不允許抓取，跳過：%s", url)
        return None

    response = common.polite_get(url, logger, common.RATE_LIMIT_SUPPLY_CHAIN)
    if response is not None:
        return response.text

    # 注意：common.polite_get() 遇到 SSL 驗證失敗時會提早結束重試（見該函式
    # docstring），所以走到這裡通常只等了幾秒，不是真的等完整套約 30 秒的
    # backoff——這則 log 緊接著上面 polite_get() 內部已經記過的 SSL 警告
    # 出現，兩則合起來讓學員在頁面還沒卡住太久時就知道發生什麼事、接下來
    # 會怎麼處理，而不是盯著終端機空等一段時間才看到一行錯誤。
    logger.warning(
        "requests 依標準流程仍失敗，改用系統 curl 指令備援：%s\n"
        "已知情況：ic.tpex.org.tw 的憑證鏈在部分環境（例如較新版 Python）"
        "無法通過 Python 端 TLS 驗證，這不是網站故障；若這正是本次失敗的"
        "原因，改用系統 curl 就能正常取得頁面（curl 一樣會完整驗證憑證，"
        "沒有加 -k/--insecure，詳見模組 docstring）。",
        url,
    )
    return _fetch_via_curl(url, common.USER_AGENT)


# ---------------------------------------------------------------------
# 清理／解析（純函式，不做 I/O，方便單獨測試）
# ---------------------------------------------------------------------
def _normalize_company_symbol(href: str) -> str | None:
    """從公司連結網址取出股票代號，正規化成純數字字串；抓不到就回傳 None。

    做什麼＋為什麼：
        頁面上的公司連結有兩種：
        1. 本國/外國「上市／上櫃／興櫃／創櫃」公司：連結格式為
           `company_basic.php?stk_code=2330`，代表這是有股票代號的公司。
        2. 「知名外國企業」：連結直接指到該公司官網（如
           `http://www.broadcom.com/`），沒有 stk_code 參數，代表這是
           未在台掛牌、沒有台股代號的公司。

    注意（禁止捏造資料）：
        如果 stk_code 抓到的值不是純數字（理論上不該發生，但網頁結構
        以後可能改版），一律當作「抓不到代號」回傳 None，絕不硬塞一個
        猜測值進資料庫。
    """
    query = parse_qs(urlparse(href).query)
    values = query.get("stk_code")
    if not values or not values[0]:
        return None
    code = values[0].strip()
    return code if code.isdigit() else None


def _build_relation_map(soup: BeautifulSoup) -> dict[str, str]:
    """從頁面的「上游/中游/下游」區塊，建立 segment 代碼 → relation 的對照表。

    做什麼＋為什麼：
        頁面用 `<div class="chain">` 把每個大分類（上游/中游/下游）包起來，
        底下每個 `<div class="company-chain-panel" id="ic_link_XXXX">` 是
        一個細分環節（segment）的按鈕，id 的 XXXX 部分之後會拿來對應
        `<div id="companyList_XXXX">`（實際公司清單放的地方）。分兩步驟
        （先建對照表，再解析公司清單，見 parse_supply_chain）比「邊解析
        公司清單邊判斷 relation」清楚，兩件事分開寫，各自都好懂好測。
    """
    relation_map: dict[str, str] = {}
    for chain_div in soup.select("div.chain"):
        title_el = chain_div.select_one(".chain-title-panel")
        if title_el is None:
            continue
        label = title_el.get_text(strip=True)
        relation = RELATION_LABELS.get(label)
        if relation is None:
            # 注意：出現不認識的分類標題，寧可跳過也不要亂猜對應到哪個 relation。
            logger.warning("無法辨識的產業鏈分類標題，跳過：%r", label)
            continue
        for panel in chain_div.select("div.company-chain-panel[id]"):
            segment_code = panel["id"].removeprefix("ic_link_")
            relation_map[segment_code] = relation
    return relation_map


def parse_supply_chain(html: str, source_url: str = TPEX_URL) -> list[dict]:
    """純函式：解析 TPEx 產業價值鏈頁面 HTML，回傳待寫入資料庫的 rows。

    回傳的每筆 dict 直接符合 StockRepository.upsert_supply_chain() 要求的
    欄位（anchor_symbol, company_name, company_symbol, relation, segment,
    source_url），呼叫端不需要再另外轉換。

    注意（禁止捏造資料）：
        任何一步解析不到預期結構（找不到分類標題、找不到公司清單、
        公司名稱是空字串……）都只記 log 跳過那一筆／那個區塊，絕不用
        空字串或猜測值頂替。

    注意（schema 的已知限制，非本函式的邏輯錯誤）：
        資料庫的去重鍵是 (anchor_symbol, company_name, segment)，不包含
        relation。頁面上「生產製程及檢測設備」這個 segment 名稱同時出現在
        中游與下游兩個大分類底下，若同一家公司剛好兩邊都有列（實測約 32
        家），後處理的那筆 upsert 會把 relation 蓋成後面的值。這是資料庫
        schema 設計本身的取捨（db/base.py 屬鎖定介面，不在本檔案調整
        範圍），此處僅忠實反映頁面資料、不試圖用程式碼掩蓋這個限制。
    """
    soup = BeautifulSoup(html, "html.parser")
    relation_map = _build_relation_map(soup)
    if not relation_map:
        logger.error("頁面解析不到任何「上游/中游/下游」分類，可能改版了，放棄本次解析")
        return []

    rows: list[dict] = []
    seen_segment_codes: set[str] = set()

    for segment_code, relation in relation_map.items():
        # 這裡防的是「relation_map 這個 dict 裡意外出現重複 key」，但 dict
        # 的 key 本來就不會重複，實務上這個 if 永遠不會成立，是防禦性寫法。
        # 真正處理「同一個 companyList 區塊在 DOM 裡出現兩次（桌機／行動
        # 裝置各一份，內容相同，用 CSS 切換顯示）」的地方是下面
        # `soup.find(id=...)`——它只取第一個符合的元素。
        #
        # 注意（教訓，之前這裡的註解寫錯了）：以上兩種去重都只處理「整個
        # 區塊重複」的情況，不處理「同一個 (relation, segment) 底下，
        # 同一家公司在單一份公司清單裡本身就重複列出好幾次」——這是實測
        # 觀察到的真實現象（頁面在同一份清單裡依「本國上市／上櫃／興櫃／
        # 創櫃板」等子分類分別列出公司，同一家公司若橫跨多個子分類，同名
        # 連結最多會重複出現到 7 次），必須另外處理，不能假裝「不需要
        # 另外寫過濾邏輯」，見下面的 deduplicate_rows()。
        if segment_code in seen_segment_codes:
            continue
        seen_segment_codes.add(segment_code)

        company_list_div = soup.find(id=f"companyList_{segment_code}")
        if company_list_div is None:
            logger.warning("找不到 segment %s 對應的公司清單區塊，跳過", segment_code)
            continue

        segment_name = company_list_div.get("title", "").strip() or None

        links = company_list_div.select("a[href]")
        if not links:
            logger.info("segment %s（%s）目前沒有列出任何公司", segment_code, segment_name)
            continue

        for link in links:
            company_name = link.get_text(strip=True)
            if not company_name:
                logger.warning("segment %s 有一筆公司名稱是空的，跳過", segment_code)
                continue
            company_symbol = _normalize_company_symbol(link.get("href", ""))
            rows.append(
                {
                    "anchor_symbol": ANCHOR_SYMBOL,
                    "company_name": company_name,
                    "company_symbol": company_symbol,
                    "relation": relation,
                    "segment": segment_name,
                    "source_url": source_url,
                }
            )

    return rows


def deduplicate_rows(rows: list[dict]) -> list[dict]:
    """對 parse_supply_chain() 的輸出，依 (relation, segment, company_name) 去重。

    做什麼＋為什麼：
        實測發現同一個 (relation, segment) 底下，同一家公司名稱最多會
        重複出現到 7 次——原因是頁面在同一份公司清單裡，依「本國上市
        公司／上櫃公司／興櫃公司／創櫃板公司」等子分類分別列出，同一家
        公司剛好橫跨多個子分類時，就會在同一個 <table> 裡出現好幾次同名
        連結。parse_supply_chain() 本身刻意保持「頁面上有什麼就照實解析
        出什麼」（不在解析階段動手腳過濾掉重複），去重統一交給這個獨立
        函式處理——「解析」與「去重」兩件事拆開，各自都好懂好測，也讓
        呼叫端（run()）能分別記錄解析筆數與去重後筆數，不會把兩件事的
        數字混在一起，造成「爬蟲說寫入 610 筆，資料庫卻只有 479 列」這種
        讓學員誤以為程式有 bug 的落差。

    保留策略：
        同一個 key 重複出現時保留第一筆——同一家公司在同一個 (relation,
        segment) 底下，company_symbol 理論上應該一致，保留哪一筆通常不
        影響結果；保留「第一筆」是比較保守的選擇，不會用後面子分類裡
        可能有差異的資料覆蓋掉先解析到的值。
    """
    seen: set[tuple[str, str | None, str]] = set()
    deduped: list[dict] = []
    for row in rows:
        key = (row["relation"], row.get("segment"), row["company_name"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


# ---------------------------------------------------------------------
# 主流程（I/O：抓頁 → 解析 → 去重 → 寫入資料庫）
# ---------------------------------------------------------------------
def run() -> None:
    """完整流程：抓頁 → 解析 → 去重 → 寫入資料庫，並記錄三段式摘要統計。"""
    logger.info("開始抓取台積電（%s）上下游供應鏈：%s", ANCHOR_SYMBOL, TPEX_URL)

    html = fetch_supply_chain_page(TPEX_URL)
    if html is None:
        logger.error("抓不到頁面內容，本次爬取中止（不寫入任何資料）")
        return

    parsed_rows = parse_supply_chain(html, source_url=TPEX_URL)
    if not parsed_rows:
        logger.warning("解析結果是空的，可能頁面改版或本次沒有取得任何公司資料，不寫入")
        return

    rows = deduplicate_rows(parsed_rows)

    repo = get_repository()
    written = repo.upsert_supply_chain(rows)

    by_relation: dict[str, int] = {}
    for row in rows:
        by_relation[row["relation"]] = by_relation.get(row["relation"], 0) + 1

    # 「寫入(新增或更新) N 筆」是這次執行動了幾筆，不等於資料庫裡目前總共
    # 有幾筆（例如這次全部都是更新既有列，寫入筆數會等於這次筆數，但不
    # 代表資料庫總數因此改變）。直接從 repo 讀回目前這個 anchor 的實際
    # 總列數一併印出，避免學員把「解析／去重／寫入」三個數字誤當成資料庫
    # 應該有的總筆數。
    total_in_db = len(repo.get_supply_chain(ANCHOR_SYMBOL))

    logger.info(
        "供應鏈爬取完成：解析 %d 筆／去重後 %d 筆／資料庫寫入(新增或更新) %d 筆"
        "（上游 %d／中游 %d／下游 %d）；資料庫目前 anchor=%s 實際總列數：%d",
        len(parsed_rows),
        len(rows),
        written,
        by_relation.get("upstream", 0),
        by_relation.get("midstream", 0),
        by_relation.get("downstream", 0),
        ANCHOR_SYMBOL,
        total_in_db,
    )


def main() -> None:
    """CLI 入口：`venv/bin/python -m crawlers.supply_chain_crawler`。

    這支爬蟲目前沒有可調參數（來源固定一頁、anchor 固定 2330），
    仍掛上 argparse 是為了和另外兩支爬蟲行為一致：`--help` 能看到說明、
    傳錯參數會報錯，而不是被靜默忽略後直接開跑。
    """
    parser = argparse.ArgumentParser(
        description="抓取 TPEx 產業價值鏈平台的半導體上下游公司並寫入資料庫（anchor=2330 台積電）"
    )
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
