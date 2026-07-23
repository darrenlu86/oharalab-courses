"""pytest 共用 fixture：repo 根路徑注入 sys.path、全新測試資料庫。

全 repo 只有這一份 conftest.py（SPEC §7：單一 pytest 入口），
六個 stage 的測試都從這裡拿 fresh_db / repo_root，不要各自重寫一份。
"""

import sqlite3
import sys
from pathlib import Path

import pytest

# 把 repo 根目錄加進 sys.path，讓測試可以直接 `import common`、
# `import scripts.init_db`、`import stage2_eda.weather_eda` 等等，
# 不受 pytest 執行時目前工作目錄影響。
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.init_db import build_database  # noqa: E402（需先調整 sys.path）


@pytest.fixture
def repo_root() -> Path:
    """repo 根目錄的絕對路徑，測試需要組路徑時用這個，不要寫死相對路徑。"""
    return REPO_ROOT


@pytest.fixture
def fresh_db(tmp_path) -> Path:
    """在 tmp_path 建一個全新的 SQLite 資料庫，跑過 init_db 的建表邏輯
    （建五張表＋匯入三個預設測站），回傳資料庫檔案路徑。

    每個測試都拿到獨立的全新檔案，測試之間不會互相污染，
    也不會動到 repo 裡真正的 data/weather_course.db。
    """
    db_path = tmp_path / "test_weather_course.db"
    build_database(db_path)
    return db_path


@pytest.fixture
def fresh_db_conn(fresh_db) -> sqlite3.Connection:
    """fresh_db 的現成連線版本，測試想直接下 SQL 查詢時可以少寫一行 connect。"""
    conn = sqlite3.connect(fresh_db)
    yield conn
    conn.close()
