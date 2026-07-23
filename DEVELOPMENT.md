# DEVELOPMENT.md — 開發者視角

給要修改、擴充、或維護這個課程 repo 的人看。學員視角的「怎麼學」在
`README.md` 與各階段的 `README.md`；這裡講「repo 怎麼運作、怎麼安全地
改它」。

## 架構總覽

完整架構圖（含服務、資料流向）在 [`docs/PRD.md`](docs/PRD.md)。摘要：

- **共用層**：`common/`（路徑/字型）、`data/`（CSV，committed）、
  `scripts/`（一次性資料生成腳本）——全部六個階段共用，不要在階段目錄
  裡複製一份。
- **教具服務**：`sandbox_site/`（stage3 爬蟲標的）、
  `stage1_api_app/mock_ai_server.py`（stage1 mock AI）——這兩個是「為了
  教學而存在的假服務」，不是本課程的核心產出。
- **六個階段**：各自獨立可執行，但共用同一個 SQLite schema
  （`scripts/init_db.py` 的 `SCHEMA_SQL`，唯一真實來源）。

## 資料流依賴關係

```
data/raw/*.csv  ──┬──> stage2_eda（EDA）
                   ├──> stage4_ml_structured（特徵工程/建模）
                   └──> sandbox_site（/records /api/latest 頁面內容）

data/synthetic/*.csv ──┬──> sandbox_site（/comments /announcements 頁面內容）
                        └──> stage5_ml_unstructured 案例 A（情感分類語料）

sandbox_site（需啟動） ──> stage3_crawler ──> data/weather_course.db

stage4/5 的 *.joblib（gitignored） ──> stage6_system（透過 pipeline/bootstrap.py 確保存在）
```

**改資料前務必想清楚影響範圍**：`data/raw/*.csv` 被 stage2/stage4/
sandbox_site 三處同時讀取，改欄位或重新抓取前，先確認這三處的假設
（欄名、單位、缺值處理）都還成立。

## 各階段程式碼組織慣例

- 每個階段目錄的邏輯都拆成「純函式模組」（例如
  `stage2_eda/weather_eda.py`、`stage4_ml_structured/features.py`）+
  「CLI/腳本入口」（例如 `train.py`/`predict.py`）——純函式模組沒有
  I/O 副作用，方便 `tests/` 直接 import 測試；CLI 入口才處理
  print/argparse/檔案讀寫。新增功能時延續這個切分，不要把邏輯直接寫在
  `if __name__ == "__main__":` 底下。
- 跨階段重用優先於複製：`stage6_system` 大量 import
  `stage4_ml_structured`/`stage5_ml_unstructured`/`stage3_crawler` 的
  函式（模型、db、特徵工程），而不是重寫一份。加新階段或改既有階段時，
  先檢查其他階段有沒有現成的函式可以 import，不要複製貼上。
- 路徑一律用 `common.paths` 或各階段自己往上找 `requirements.txt`/
  `__file__` 推導絕對路徑，不要寫死相對路徑或依賴 `os.getcwd()`——這在
  notebook/pytest/CLI 三種執行情境的當前工作目錄都不一樣，寫死相對路徑
  一定會在其中一種情境炸掉（`stage2_eda/analysis.ipynb` 開發時真的踩過
  這個坑，見該階段 `report.md`）。

## 資料庫 schema 變更

`data/weather_course.db` 的 schema 定義**只有一份真實來源**：
`scripts/init_db.py` 的 `SCHEMA_SQL`。要改 schema：

1. 改 `SCHEMA_SQL`（用 `CREATE TABLE IF NOT EXISTS`，不要用會破壞既有
   資料的寫法）。
2. 同步檢查 `stage3_crawler/crawler/db.py`、`stage6_system/app.py`、
   `stage6_system/pipeline/*.py` 裡直接寫 SQL 的地方（`INSERT`/
   `SELECT` 語句），schema 改了但這些地方沒同步改，會在執行期才報錯，
   不會有編譯期檢查。
3. 刪除本機的 `data/weather_course.db`（gitignored，可以放心刪）並重新
   `venv/bin/python scripts/init_db.py --reset` 或
   `venv/bin/python -m stage6_system.pipeline.bootstrap` 驗證新 schema
   真的可以從零建立。
4. 更新 `docs/PRD.md` 的 ER 圖與 schema 說明（那份文件的 schema 只是
   視覺化，若與程式碼不一致以程式碼為準，但放著不同步會誤導讀者）。

## 測試怎麼跑

```bash
venv/bin/python -m pytest -q          # 全部（163 個，2026-07-24 實測 ~20 秒）
venv/bin/python -m pytest tests/test_stage4_ml_structured.py -v   # 單一階段
```

`tests/conftest.py` 提供兩個共用 fixture：

- `repo_root`：repo 根目錄絕對路徑。
- `fresh_db` / `fresh_db_conn`：`tmp_path` 底下全新的 SQLite（已跑過
  `init_db` 建表 + 匯入三個預設測站），每個測試獨立，不會互相污染，也
  不會動到真正的 `data/weather_course.db`。

**涉及網路的程式碼一律要能注入假 session/client**（`requests`-like
物件或 FastAPI `TestClient`），測試才能在不連外網的前提下驗證邏輯——
見 `stage1_api_app/weather_brief.py` 的 `fetch_forecast(session=...)`、
`stage3_crawler/crawler/http_client.py` 的 `PoliteSession`、
`stage6_system/pipeline/update_data.py` 的 `update_city_from_api
(session=...)`，新增任何打 API 的程式碼都要延續這個模式。

**FastAPI 路由的依賴注入模式**（`stage6_system/app.py`）：資料庫連線與
模型都透過 `Depends()` 注入，測試用 `app.dependency_overrides` 換成假
資料庫/假模型（見 `tests/test_stage6_system.py`）。注意：TestClient 對
sync def 路由是丟進 worker thread 執行，測試用的 SQLite 連線如果是在
pytest 主執行緒建立、再傳進去，要加 `check_same_thread=False`，否則會
撞到 SQLite 的同執行緒保護（這個坑真的踩過，見
`stage6_system/report.md`）。

**ML 訓練程式碼的測試策略**：不追求數字重現（隨機森林等演算法的確切
輸出可能因 sklearn 版本而有微小差異），只驗證：特徵工程的邏輯正確性
（用真實資料的已知性質斷言，例如「lag_1 必須等於今天的值」）、
train 函式跑得通且回傳的 schema 正確、指標落在合理範圍
（如 `0<=accuracy<=1`）。真正的效能數字寫在各階段 `report.md`，那是
「跑過一次的實測記錄」，不是測試斷言的對象。

## 模型與資料庫檔案（gitignored）

`*.joblib`、`data/*.db`、`stage3_crawler/output/` 都不進版控（見
`.gitignore`）。這些檔案全部可以用對應腳本重新產生：

| 檔案 | 重新產生方式 |
|---|---|
| `data/weather_course.db` | `scripts/init_db.py` + 跑過 stage3/6 的資料寫入流程 |
| `stage4_ml_structured/models/*.joblib` | `venv/bin/python -m stage4_ml_structured.train` |
| `stage5_ml_unstructured/models/*.joblib` | `venv/bin/python -m stage5_ml_unstructured.train_text`／`train_digits` |
| `stage3_crawler/output/*.csv` | `venv/bin/python -m stage3_crawler.export_csv`（需要資料庫已有資料） |

刪掉本機這些檔案不會影響 git 狀態，重新跑對應指令就能復原——這是刻意
設計，不要嘗試把它們加進版控。

## 新增第七個階段（如果你要擴充課程）

1. 新增 `stageN_xxx/` 目錄，內含 `__init__.py`、程式碼、`README.md`、
   `report.md`、`slides.md`（照 `stage1_api_app/` 或其他階段的目錄結構
   抄一份骨架）。
2. `README.md` 固定章節（見 SPEC §5，或抄現有階段的章節順序）：這一關
   在教什麼／你會學到／完成後產出對照表／前置需求／快速開始／逐步教學／
   為什麼這樣設計／注意／驗收 checklist／延伸挑戰。
3. 邏輯拆成純函式模組 + CLI 入口（見上方「各階段程式碼組織慣例」）。
4. `tests/test_stageN_xxx.py` 對應測試檔案，需要固定樣本的話放
   `tests/fixtures/stageN_xxx/`。
5. 更新 `docs/CURRICULUM.md` 的六階段對應表（改成七階段）與前置關係圖。
6. 更新本檔與 `README.md` 的目錄結構說明。
