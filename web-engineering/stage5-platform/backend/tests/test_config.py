"""
SECRET_KEY 預設值偵測 helper 的測試。

刻意不啟動整個 FastAPI app、也不去解析 uvicorn 啟動時印在終端機的 stderr——
那樣測試會很脆弱（依賴印出時機、依賴有沒有其他地方也在寫 stderr）。這裡只針對
app/config.py 提供的兩支函式各自驗證：`is_default_secret_key()` 的純判斷邏輯，
以及 `warn_if_default_secret_key()` 在符合/不符合條件時是否真的有/沒有印出警告。
"""

from app.config import DEFAULT_SECRET_KEY, is_default_secret_key, warn_if_default_secret_key


def test_is_default_secret_key_detects_the_default_value():
    assert is_default_secret_key(DEFAULT_SECRET_KEY) is True


def test_is_default_secret_key_rejects_a_custom_value():
    assert is_default_secret_key("a-real-randomly-generated-secret-abc123") is False


def test_is_default_secret_key_rejects_empty_string():
    # 空字串本身也不安全（等同沒設定），但它不是「預設值」，這支函式只負責判斷
    # 「是不是那個公開刊在原始碼裡的字串」，不負責判斷「安全與否」的其他情況。
    assert is_default_secret_key("") is False


def test_warn_if_default_secret_key_prints_warning_when_using_default(capsys):
    warn_if_default_secret_key(DEFAULT_SECRET_KEY)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "SECRET_KEY" in captured.err
    assert "openssl rand -hex 32" in captured.err
    assert "admin" in captured.err


def test_warn_if_default_secret_key_silent_when_using_custom_value(capsys):
    warn_if_default_secret_key("a-real-randomly-generated-secret-abc123")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
