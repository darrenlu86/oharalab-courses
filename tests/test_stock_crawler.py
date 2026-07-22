"""
tests/test_stock_crawler.py — crawlers/stock_crawler.py 的單元測試。

做什麼：
    只測試「清理純函式」（民國年轉換、千分位轉數字、漲跌價差解析、
    整列清理 clean_daily_row）與「月份計算純函式」，以及用固定 fixture
    JSON 檔驗證 fetch_month() 的解析邏輯——完全不打真實網路。

為什麼這樣設計（不打網路）：
    這些測試要能在離線環境、CI 環境穩定重複執行，不依賴 TWSE 網站當下
    是否正常回應。真正打網路驗證的部分（實際跑一次爬蟲、比對 TWSE 原始
    回應）留在任務驗收時的手動 CLI 執行，不寫進自動化測試。

fixture 說明（tests/fixtures/，皆為 2026-07-23 實測 TWSE API 的真實回應
原文存檔，未經竄改）：
    - twse_stock_day_202607.json：一般月份，15 筆交易日，含正常漲跌。
    - twse_stock_day_202606_x_anomaly.json：21 筆交易日，其中 6/11 那筆
      漲跌價差是 "X0.00"（除權息基準價調整日），用來驗證 X 前綴解析。
    - twse_stock_day_no_data.json：查詢未來月份時 TWSE 回傳的格式
      （stat 不是 "OK"，沒有 data 欄位），用來驗證「這個月沒有資料」
      的分支不會被誤判成錯誤。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawlers import stock_crawler  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str) -> dict:
    path = FIXTURES_DIR / name
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# =====================================================================
# convert_roc_date
# =====================================================================


class TestConvertRocDate:
    def test_normal_date(self):
        assert stock_crawler.convert_roc_date("115/07/01") == "2026-07-01"

    def test_single_digit_month_day(self):
        # 注意：TWSE 實際回應月/日不補零（如 "115/1/1"），輸出仍要補零成
        # 兩位數的 ISO 格式，方便字串排序與跟其他資料源比較。
        assert stock_crawler.convert_roc_date("115/1/1") == "2026-01-01"

    def test_empty_string_returns_none(self):
        assert stock_crawler.convert_roc_date("") is None

    def test_none_returns_none(self):
        assert stock_crawler.convert_roc_date(None) is None

    def test_wrong_format_returns_none(self):
        assert stock_crawler.convert_roc_date("2026-07-01") is None

    def test_non_numeric_returns_none(self):
        assert stock_crawler.convert_roc_date("abc/07/01") is None

    def test_month_out_of_range_returns_none(self):
        # 審查驗收範例：115/13/01（13 月不存在）。
        assert stock_crawler.convert_roc_date("115/13/01") is None

    def test_month_zero_returns_none(self):
        assert stock_crawler.convert_roc_date("115/00/15") is None

    def test_day_out_of_range_returns_none(self):
        assert stock_crawler.convert_roc_date("115/07/32") is None

    def test_day_zero_returns_none(self):
        assert stock_crawler.convert_roc_date("115/07/00") is None


# =====================================================================
# parse_number / parse_int
# =====================================================================


class TestParseNumber:
    def test_thousands_separator(self):
        assert stock_crawler.parse_number("37,544,470") == 37544470.0

    def test_price_with_comma_and_decimal(self):
        assert stock_crawler.parse_number("2,495.00") == 2495.0

    def test_double_dash_returns_none(self):
        assert stock_crawler.parse_number("--") is None

    def test_empty_string_returns_none(self):
        assert stock_crawler.parse_number("") is None

    def test_none_returns_none(self):
        assert stock_crawler.parse_number(None) is None

    def test_garbage_returns_none(self):
        assert stock_crawler.parse_number("N/A") is None


class TestParseInt:
    def test_thousands_separator_to_int(self):
        assert stock_crawler.parse_int("111,091") == 111091
        assert isinstance(stock_crawler.parse_int("111,091"), int)

    def test_double_dash_returns_none(self):
        assert stock_crawler.parse_int("--") is None


# =====================================================================
# parse_change（漲跌價差，含 X 前綴）
# =====================================================================


class TestParseChange:
    def test_positive(self):
        assert stock_crawler.parse_change("+95.00") == 95.0

    def test_negative(self):
        assert stock_crawler.parse_change("-40.00") == -40.0

    def test_x_prefix_is_zero(self):
        # 實測結論：TWSE 的 X 前綴（除權息基準價調整日）一律搭配 "X0.00"，
        # 依規格書 §5a 決定解析為 0.0（詳見 stock_crawler.parse_change 內註解）。
        assert stock_crawler.parse_change("X0.00") == 0.0

    def test_double_dash_returns_none(self):
        assert stock_crawler.parse_change("--") is None

    def test_empty_returns_none(self):
        assert stock_crawler.parse_change("") is None

    def test_none_returns_none(self):
        assert stock_crawler.parse_change(None) is None


# =====================================================================
# clean_daily_row（整列清理）
# =====================================================================


class TestCleanDailyRow:
    def test_normal_row(self):
        raw_row = [
            "115/07/01", "37,544,470", "93,600,076,825", "2,495.00",
            "2,505.00", "2,475.00", "2,505.00", "+95.00", "111,091", "",
        ]
        result = stock_crawler.clean_daily_row("2330", raw_row)
        assert result == {
            "stock_symbol": "2330",
            "trade_date": "2026-07-01",
            "open": 2495.0,
            "high": 2505.0,
            "low": 2475.0,
            "close": 2505.0,
            "volume": 37544470,
            "turnover": 93600076825,
            "transactions": 111091,
            "change": 95.0,
        }

    def test_x_prefix_change_row(self):
        raw_row = [
            "115/06/11", "46,417,523", "104,091,484,739", "2,240.00",
            "2,260.00", "2,210.00", "2,250.00", "X0.00", "320,151", "",
        ]
        result = stock_crawler.clean_daily_row("2330", raw_row)
        assert result["change"] == 0.0
        assert result["trade_date"] == "2026-06-11"

    def test_bad_date_skips_whole_row(self):
        raw_row = [
            "bad-date", "37,544,470", "93,600,076,825", "2,495.00",
            "2,505.00", "2,475.00", "2,505.00", "+95.00", "111,091", "",
        ]
        assert stock_crawler.clean_daily_row("2330", raw_row) is None

    def test_missing_price_skips_whole_row(self):
        # 開盤價是 "--"（缺值）→ 必要欄位缺漏，整列跳過，不可以拿 0 頂替。
        raw_row = [
            "115/07/01", "37,544,470", "93,600,076,825", "--",
            "2,505.00", "2,475.00", "2,505.00", "+95.00", "111,091", "",
        ]
        assert stock_crawler.clean_daily_row("2330", raw_row) is None

    def test_change_missing_does_not_skip_row(self):
        # change 缺值是合法的，不應該連累其他欄位都齊全的這一列被丟棄。
        raw_row = [
            "115/07/01", "37,544,470", "93,600,076,825", "2,495.00",
            "2,505.00", "2,475.00", "2,505.00", "--", "111,091", "",
        ]
        result = stock_crawler.clean_daily_row("2330", raw_row)
        assert result is not None
        assert result["change"] is None

    def test_too_few_fields_skips_row(self):
        assert stock_crawler.clean_daily_row("2330", ["115/07/01"]) is None


# =====================================================================
# 月份計算純函式
# =====================================================================


class TestMonthMath:
    def test_month_start(self):
        assert stock_crawler.month_start(date_(2026, 7, 15)) == date_(2026, 7, 1)

    def test_add_months_forward(self):
        assert stock_crawler.add_months(date_(2026, 7, 1), 1) == date_(2026, 8, 1)

    def test_add_months_year_rollover_forward(self):
        assert stock_crawler.add_months(date_(2026, 12, 1), 1) == date_(2027, 1, 1)

    def test_add_months_backward(self):
        assert stock_crawler.add_months(date_(2026, 7, 1), -2) == date_(2026, 5, 1)

    def test_add_months_year_rollover_backward(self):
        assert stock_crawler.add_months(date_(2026, 1, 1), -1) == date_(2025, 12, 1)

    def test_determine_start_month_no_checkpoint(self):
        # 無 checkpoint、--months 3 → 從「今天所在月往前推 2 個月」開始。
        today = date_(2026, 7, 23)
        start = stock_crawler.determine_start_month(None, 3, today)
        assert start == date_(2026, 5, 1)

    def test_determine_start_month_with_checkpoint(self):
        # 有 checkpoint（最新資料在 6 月中）→ 從 6 月第一天重抓，不是 7 月。
        today = date_(2026, 7, 23)
        start = stock_crawler.determine_start_month("2026-06-15", 3, today)
        assert start == date_(2026, 6, 1)

    def test_iter_months_inclusive(self):
        months = list(stock_crawler.iter_months(date_(2026, 5, 1), date_(2026, 7, 23)))
        assert months == [date_(2026, 5, 1), date_(2026, 6, 1), date_(2026, 7, 1)]

    def test_iter_months_single_month(self):
        months = list(stock_crawler.iter_months(date_(2026, 7, 1), date_(2026, 7, 1)))
        assert months == [date_(2026, 7, 1)]


def date_(year: int, month: int, day: int):
    from datetime import date

    return date(year, month, day)


# =====================================================================
# fetch_month（用固定 fixture JSON，mock 掉 polite_get，不打網路）
# =====================================================================


class TestFetchMonth:
    def test_normal_month_parses_all_rows(self):
        payload = load_fixture("twse_stock_day_202607.json")
        mock_response = Mock()
        mock_response.json.return_value = payload

        with patch.object(stock_crawler, "polite_get", return_value=mock_response), \
             patch.object(stock_crawler, "check_robots_allowed", return_value=True):
            rows = stock_crawler.fetch_month("2330", date_(2026, 7, 1))

        assert rows is not None
        assert len(rows) == len(payload["data"])
        assert all(row["stock_symbol"] == "2330" for row in rows)
        assert all(row["trade_date"].startswith("2026-07-") for row in rows)

    def test_x_anomaly_month_change_is_zero(self):
        payload = load_fixture("twse_stock_day_202606_x_anomaly.json")
        mock_response = Mock()
        mock_response.json.return_value = payload

        with patch.object(stock_crawler, "polite_get", return_value=mock_response), \
             patch.object(stock_crawler, "check_robots_allowed", return_value=True):
            rows = stock_crawler.fetch_month("2330", date_(2026, 6, 1))

        assert rows is not None
        x_day = next(r for r in rows if r["trade_date"] == "2026-06-11")
        assert x_day["change"] == 0.0

    def test_no_data_month_returns_empty_list(self):
        payload = load_fixture("twse_stock_day_no_data.json")
        mock_response = Mock()
        mock_response.json.return_value = payload

        with patch.object(stock_crawler, "polite_get", return_value=mock_response), \
             patch.object(stock_crawler, "check_robots_allowed", return_value=True):
            rows = stock_crawler.fetch_month("2330", date_(2026, 9, 1))

        assert rows == []

    def test_robots_disallowed_returns_none(self):
        with patch.object(stock_crawler, "check_robots_allowed", return_value=False):
            rows = stock_crawler.fetch_month("2330", date_(2026, 7, 1))
        assert rows is None

    def test_request_failure_returns_none(self):
        with patch.object(stock_crawler, "polite_get", return_value=None), \
             patch.object(stock_crawler, "check_robots_allowed", return_value=True):
            rows = stock_crawler.fetch_month("2330", date_(2026, 7, 1))
        assert rows is None

    def test_single_bad_row_does_not_abort_whole_month(self):
        # 壞資料的型別不對（日期欄位是 int 而非 str），會讓 clean_daily_row()
        # 內部呼叫 .strip() 時真的拋出 AttributeError（不是回傳 None 那種
        # 「正常判斷格式不對」的情況），用來驗證 fetch_month() 的逐筆
        # try/except 真的攔得住意料之外的例外，其餘好資料仍全數清理成功。
        payload = load_fixture("twse_stock_day_202607.json")
        bad_row = [20260701, "1", "1", "1", "1", "1", "1", "+1.00", "1", ""]
        corrupted_payload = {**payload, "data": [*payload["data"], bad_row]}
        mock_response = Mock()
        mock_response.json.return_value = corrupted_payload

        with patch.object(stock_crawler, "polite_get", return_value=mock_response), \
             patch.object(stock_crawler, "check_robots_allowed", return_value=True):
            rows = stock_crawler.fetch_month("2330", date_(2026, 7, 1))

        assert rows is not None
        # 壞的那一筆被跳過，其餘好資料（原本 fixture 的筆數）全數清理成功。
        assert len(rows) == len(payload["data"])


# =====================================================================
# crawl()：串接 fetch_month + repository，用 tmp db（來自 conftest 的 repo fixture）
# =====================================================================


class TestCrawlIntegration:
    def test_crawl_writes_rows_and_is_idempotent(self, repo, monkeypatch):
        repo.upsert_stock("2330", "台積電", market="上市", industry="半導體")
        payload = load_fixture("twse_stock_day_202607.json")
        # 注意：today 固定寫死成跟 fixture 資料同一個月（fixture 最後一筆是
        # 2026-07-22），而不是讀取真正的系統日期——這樣測試結果不會因為
        # 「今天剛好是哪一天」而變動，之後任何時間重跑都會得到同樣結果。
        fixed_today = date_(2026, 7, 23)

        monkeypatch.setattr(stock_crawler, "get_repository", lambda: repo)
        monkeypatch.setattr(stock_crawler, "check_robots_allowed", lambda url: True)

        def fake_fetch_month(stock_symbol, month_first_day):
            return [
                row
                for row in (
                    stock_crawler.clean_daily_row(stock_symbol, raw)
                    for raw in payload["data"]
                )
                if row is not None
            ]

        monkeypatch.setattr(stock_crawler, "fetch_month", fake_fetch_month)

        first_run = stock_crawler.crawl(months=1, stock_symbol="2330", today=fixed_today)
        assert first_run == len(payload["data"])

        second_run = stock_crawler.crawl(months=1, stock_symbol="2330", today=fixed_today)
        # 冪等：同樣的資料再寫一次，筆數（新增或更新）不變，且資料庫總列數不變。
        assert second_run == len(payload["data"])

        stored = repo.get_daily_prices("2330")
        assert len(stored) == len(payload["data"])
