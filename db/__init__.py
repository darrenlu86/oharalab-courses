"""db 套件：資料存取層（repository pattern）。

爬蟲層與 Dashboard 層都只透過 `StockRepository` 這個抽象介面存取資料，
不直接碰 SQL 或特定資料庫的 SDK。實際要用 SQLite 還是 Supabase，由
`db.factory.get_repository()` 依 `config.DB_BACKEND` 決定並回傳對應實作。
"""
