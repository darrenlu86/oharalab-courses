"""repo 根目錄與資料目錄的路徑常數。

所有 stage 都應該從這裡拿路徑，不要自己用相對路徑（例如 "../data"）拼，
因為 notebook、pytest、CLI 三種執行方式的當前工作目錄都不一樣，
相對路徑在其中一種情境下一定會爆炸。這裡改用 __file__ 往上推導，
不管從哪裡執行都拿得到同一個絕對路徑。
"""

from pathlib import Path

# common/paths.py 往上一層就是 repo 根目錄
REPO_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
SYNTHETIC_DIR = DATA_DIR / "synthetic"

# SQLite 資料庫檔案路徑（此檔本身不 commit，由 scripts/init_db.py 產生）
DB_PATH = DATA_DIR / "weather_course.db"
