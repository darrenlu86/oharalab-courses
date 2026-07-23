"""測試 common/paths.py（路徑推導）與 common/fonts.py（中文字型設定）。

這兩個模組被全部 stage 共用，理論上出錯會讓所有 stage 一起壞掉，
所以獨立測試檔案（SPEC §2 file tree 明列 tests/test_common.py）。
"""

import sys
import warnings
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.paths import DATA_DIR, DB_PATH, RAW_DIR, REPO_ROOT as PATHS_REPO_ROOT, SYNTHETIC_DIR  # noqa: E402
from common.fonts import CANDIDATE_FONTS, setup_chinese_font  # noqa: E402


# ---------------------------------------------------------------------------
# common/paths.py
# ---------------------------------------------------------------------------


def test_repo_root_points_to_actual_repo_root():
    # repo 根目錄底下應該找得到 requirements.txt、common/、tests/ 等已知檔案，
    # 用這個判斷比較穩，不會因為 repo 資料夾改名就誤判。
    assert PATHS_REPO_ROOT == REPO_ROOT
    assert (PATHS_REPO_ROOT / "requirements.txt").exists()
    assert (PATHS_REPO_ROOT / "common").is_dir()
    assert (PATHS_REPO_ROOT / "tests").is_dir()


def test_data_dir_and_subdirs_are_correct_relative_layout():
    assert DATA_DIR == PATHS_REPO_ROOT / "data"
    assert RAW_DIR == DATA_DIR / "raw"
    assert SYNTHETIC_DIR == DATA_DIR / "synthetic"


def test_raw_and_synthetic_dirs_exist_and_contain_expected_files():
    # 這幾份是 committed 資料，理論上任何 clone 下來的環境都該有。
    for city in ["taipei", "taichung", "kaohsiung"]:
        assert (RAW_DIR / f"{city}.csv").is_file()
    assert (SYNTHETIC_DIR / "comments.csv").is_file()
    assert (SYNTHETIC_DIR / "announcements.csv").is_file()


def test_db_path_is_under_data_dir_and_not_committed():
    assert DB_PATH == DATA_DIR / "weather_course.db"
    # 不斷言檔案存不存在（gitignored，可能有可能沒有），只斷言路徑正確、
    # 且真的落在 .gitignore 涵蓋的 data/*.db 規則範圍內。
    gitignore_text = (PATHS_REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "data/*.db" in gitignore_text


def test_paths_are_absolute():
    for p in [PATHS_REPO_ROOT, DATA_DIR, RAW_DIR, SYNTHETIC_DIR, DB_PATH]:
        assert p.is_absolute(), f"{p} 不是絕對路徑，違反 common/paths.py 的設計目的"


# ---------------------------------------------------------------------------
# common/fonts.py
# ---------------------------------------------------------------------------


def test_setup_chinese_font_returns_a_candidate_or_none():
    result = setup_chinese_font()
    assert result is None or result in CANDIDATE_FONTS


def test_setup_chinese_font_sets_unicode_minus_false_when_font_found():
    import matplotlib.pyplot as plt

    result = setup_chinese_font()
    if result is not None:
        assert plt.rcParams["axes.unicode_minus"] is False
    else:
        pytest.skip("此環境找不到任何候選中文字型，無法驗證 unicode_minus 設定")


def test_setup_chinese_font_warns_when_no_candidate_available(monkeypatch):
    # 模擬字型清單裡什麼候選字型都沒有，驗證會印警告、回傳 None，
    # 而不是靜靜失敗或丟例外。
    import common.fonts as fonts_module

    monkeypatch.setattr(
        fonts_module.fm.fontManager,
        "ttflist",
        [],
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = fonts_module.setup_chinese_font()
    assert result is None
    assert any("找不到任何候選中文字型" in str(w.message) for w in caught)


def test_candidate_fonts_list_is_non_empty_and_unique():
    assert len(CANDIDATE_FONTS) > 0
    assert len(CANDIDATE_FONTS) == len(set(CANDIDATE_FONTS))
