"""
tests/test_supply_chain_crawler.py — 驗證 supply_chain_crawler 的解析邏輯。

涵蓋範圍：
    - parse_supply_chain()：用固定的 HTML fixture（tests/fixtures/
      tpex_supply_chain.html，結構仿照實際抓下來的頁面）測解析結果，
      不打真實網路——這樣測試才會穩定、跑得快，也不會對目標網站造成負擔。
    - _normalize_company_symbol()：純函式，直接測輸入輸出（股票代號正規化）。

為什麼用固定 fixture 而不是即時抓網頁：
    真實網頁的內容會隨時間改變（公司下市、新公司加入），若測試直接打
    網路，今天測過的斷言明天可能就不成立，測試會變得不穩定。用固定的
    HTML 檔案當作「這個網站曾經長這樣」的快照，測試只驗證「給定這個
    HTML，解析邏輯有沒有正確運作」，這才是單元測試該驗證的事。
"""

from __future__ import annotations

import logging
from pathlib import Path

from crawlers.supply_chain_crawler import (
    _build_relation_map,
    _normalize_company_symbol,
    deduplicate_rows,
    parse_supply_chain,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "tpex_supply_chain.html"


def _load_fixture_html() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------
# parse_supply_chain()：整體解析行為
# ---------------------------------------------------------------
def test_parse_supply_chain_returns_expected_total_count():
    rows = parse_supply_chain(_load_fixture_html(), source_url="https://example.test/ic")
    # UP1: 2 家、MID1: 2 家（雖然 DOM 出現兩次，去重後仍是 2 家）、
    # MID2: 0 家（清單區塊不存在）、DOWN1: 1 家（另 1 家名稱空白被跳過）。
    assert len(rows) == 5


def test_parse_supply_chain_all_three_relations_present():
    rows = parse_supply_chain(_load_fixture_html())
    relations = {r["relation"] for r in rows}
    assert relations == {"upstream", "midstream", "downstream"}


def test_parse_supply_chain_relation_counts():
    rows = parse_supply_chain(_load_fixture_html())
    counts = {"upstream": 0, "midstream": 0, "downstream": 0}
    for row in rows:
        counts[row["relation"]] += 1
    assert counts == {"upstream": 2, "midstream": 2, "downstream": 1}


def test_parse_supply_chain_anchor_symbol_is_2330_for_every_row():
    rows = parse_supply_chain(_load_fixture_html())
    assert all(r["anchor_symbol"] == "2330" for r in rows)


def test_parse_supply_chain_tsmc_itself_appears_as_midstream_wafer_fab():
    # 規格書明確指出：台積電自己（2330）屬中游晶圓製造，頁面資料本來就
    # 會列出這筆，爬蟲應忠實反映，不應該過濾掉。
    rows = parse_supply_chain(_load_fixture_html())
    tsmc_rows = [r for r in rows if r["company_symbol"] == "2330"]
    assert len(tsmc_rows) == 1
    assert tsmc_rows[0]["company_name"] == "台積電"
    assert tsmc_rows[0]["relation"] == "midstream"
    assert tsmc_rows[0]["segment"] == "IC/晶圓製造"


def test_parse_supply_chain_company_name_is_stripped():
    rows = parse_supply_chain(_load_fixture_html())
    names = {r["company_name"] for r in rows}
    assert "測試下游公司" in names
    # 確認沒有殘留前後空白的版本混進結果。
    assert "  測試下游公司  " not in names


def test_parse_supply_chain_empty_company_name_is_skipped():
    rows = parse_supply_chain(_load_fixture_html())
    downstream_names = {r["company_name"] for r in rows if r["relation"] == "downstream"}
    assert downstream_names == {"測試下游公司"}


def test_parse_supply_chain_company_symbol_none_for_foreign_company_without_stk_code():
    rows = parse_supply_chain(_load_fixture_html())
    foreign_row = next(r for r in rows if r["company_name"] == "國外測試公司")
    assert foreign_row["company_symbol"] is None
    assert foreign_row["relation"] == "upstream"


def test_parse_supply_chain_duplicate_company_list_div_deduplicated():
    # companyList_MID1 在 fixture 裡故意出現兩次（模擬桌機/行動裝置各一份
    # DOM），解析結果裡台積電與測試中游公司都只能各出現一次。
    rows = parse_supply_chain(_load_fixture_html())
    mid_names = [r["company_name"] for r in rows if r["relation"] == "midstream"]
    assert sorted(mid_names) == ["台積電", "測試中游公司"]


def test_parse_supply_chain_segment_without_company_list_div_is_skipped_not_crashed():
    # MID2（缺列示區塊）在 chain 區塊裡有按鈕，但沒有對應的 companyList_MID2，
    # 應該安全跳過，不噴例外，也不會產生一筆假資料。
    rows = parse_supply_chain(_load_fixture_html())
    assert not any(r["segment"] == "缺列示區塊" for r in rows)


def test_parse_supply_chain_unrecognized_relation_label_is_excluded():
    # 「特殊游」不是 上游/中游/下游 任何一種，底下的 segment（怪環節）
    # 完全不該出現在解析結果裡。
    rows = parse_supply_chain(_load_fixture_html())
    assert not any(r["segment"] == "怪環節" for r in rows)
    assert not any(r["company_name"] == "怪環節" for r in rows)


def test_parse_supply_chain_source_url_propagated():
    rows = parse_supply_chain(_load_fixture_html(), source_url="https://example.test/ic")
    assert all(r["source_url"] == "https://example.test/ic" for r in rows)


def test_parse_supply_chain_empty_html_returns_empty_list_not_crash():
    rows = parse_supply_chain("<html><body>沒有任何產業鏈區塊</body></html>")
    assert rows == []


# ---------------------------------------------------------------
# _build_relation_map()：中介對照表
# ---------------------------------------------------------------
def test_build_relation_map_maps_segment_codes_to_relations():
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(_load_fixture_html(), "html.parser")
    relation_map = _build_relation_map(soup)
    assert relation_map["UP1"] == "upstream"
    assert relation_map["MID1"] == "midstream"
    assert relation_map["MID2"] == "midstream"
    assert relation_map["DOWN1"] == "downstream"
    # 無法辨識的分類（特殊游／WEIRD）不該出現在對照表裡。
    assert "WEIRD" not in relation_map


# ---------------------------------------------------------------
# _normalize_company_symbol()：純函式
# ---------------------------------------------------------------
def test_normalize_company_symbol_extracts_digits_from_query_string():
    assert _normalize_company_symbol("company_basic.php?stk_code=2330") == "2330"


def test_normalize_company_symbol_none_when_no_stk_code_param():
    assert _normalize_company_symbol("http://www.broadcom.com/") is None


def test_normalize_company_symbol_none_when_non_numeric():
    assert _normalize_company_symbol("company_basic.php?stk_code=ABC1") is None


def test_normalize_company_symbol_none_when_empty_href():
    assert _normalize_company_symbol("") is None


# ---------------------------------------------------------------
# deduplicate_rows()：(relation, segment, company_name) 去重（項目 5 修復對象）
# ---------------------------------------------------------------
def _make_row(company_name: str, relation: str = "midstream", segment: str = "IC/晶圓製造") -> dict:
    return {
        "anchor_symbol": "2330",
        "company_name": company_name,
        "company_symbol": "1234",
        "relation": relation,
        "segment": segment,
        "source_url": "https://example.test/ic",
    }


def test_deduplicate_rows_removes_repeated_company_within_same_relation_and_segment():
    # 實測發現的真實情況：同一 (relation, segment) 底下，同一家公司因為
    # 頁面依子分類（上市/上櫃/興櫃…）重複列出，同名連結最多出現到 7 次。
    rows = [_make_row("測試公司") for _ in range(7)]
    result = deduplicate_rows(rows)
    assert len(result) == 1


def test_deduplicate_rows_keeps_same_company_name_in_different_segments():
    rows = [
        _make_row("測試公司", relation="midstream", segment="IC/晶圓製造"),
        _make_row("測試公司", relation="downstream", segment="生產製程及檢測設備"),
    ]
    result = deduplicate_rows(rows)
    # 不同 (relation, segment) 是不同的資料列，不應該被誤判成重複。
    assert len(result) == 2


def test_deduplicate_rows_keeps_first_occurrence_and_original_order():
    rows = [
        _make_row("A公司"),
        _make_row("B公司"),
        _make_row("A公司"),
    ]
    result = deduplicate_rows(rows)
    assert [r["company_name"] for r in result] == ["A公司", "B公司"]


def test_deduplicate_rows_empty_list_returns_empty_list():
    assert deduplicate_rows([]) == []


# ---------------------------------------------------------------
# common.polite_get()：SSL 錯誤提早結束重試（項目 9 修復對象）
# ---------------------------------------------------------------
# 為什麼放在這個測試檔：polite_get() 定義在 crawlers/common.py、是三支爬蟲
# 共用的函式，但這個「SSL 錯誤提早結束重試」的行為是為了解決
# supply_chain_crawler 實際遇到的 ic.tpex.org.tw 憑證鏈問題而加的（詳見該
# 模組 docstring），放在這裡最貼近實際情境、最方便日後一起維護。
def test_polite_get_ssl_error_stops_retrying_after_first_failure(monkeypatch):
    import requests as requests_module

    from crawlers import common

    call_count = {"n": 0}

    def fake_get(*args, **kwargs):
        call_count["n"] += 1
        raise requests_module.exceptions.SSLError("模擬憑證鏈驗證失敗")

    monkeypatch.setattr(common.requests, "get", fake_get)
    monkeypatch.setattr(common.time, "sleep", lambda seconds: None)  # 測試不用真的等待

    logger = logging.getLogger("test_polite_get_ssl_early_fallback")
    result = common.polite_get(
        "https://ic.tpex.org.tw/introduce.php?ic=D000", logger, 0
    )

    assert result is None
    # 只嘗試了一次就提早結束，不會像一般失敗那樣重試到第 4 次
    # （1 次初始嘗試 + 3 次 backoff）。
    assert call_count["n"] == 1


def test_polite_get_non_ssl_error_still_retries_normally(monkeypatch):
    """對照組：非 SSL 的一般請求錯誤（如連線失敗）仍要照常重試到底，
    確保 SSL 提早結束的邏輯沒有誤傷原本的重試機制。"""
    import requests as requests_module

    from crawlers import common

    call_count = {"n": 0}

    def fake_get(*args, **kwargs):
        call_count["n"] += 1
        raise requests_module.exceptions.ConnectionError("模擬連線失敗")

    monkeypatch.setattr(common.requests, "get", fake_get)
    monkeypatch.setattr(common.time, "sleep", lambda seconds: None)

    logger = logging.getLogger("test_polite_get_ssl_early_fallback")
    result = common.polite_get("https://example.test/data", logger, 0)

    assert result is None
    assert call_count["n"] == 4  # 1 次初始嘗試 + 3 次 backoff，全部照常嘗試過
