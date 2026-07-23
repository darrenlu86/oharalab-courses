"""crawlers 套件：三支爬蟲（股價／新聞／供應鏈）與共通工具（common.py）。

每支爬蟲都是獨立可執行的腳本，彼此不互相 import，只共用 common.py 提供的
robots 檢查、rate limit、重試、logging 等工具函式。爬蟲只透過
`db.factory.get_repository()` 寫入資料庫，完全不知道 Dashboard 的存在，
符合 §1 系統架構「兩段式嚴格解耦」的設計。
"""
