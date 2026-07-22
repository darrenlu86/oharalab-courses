"""測試 /api/auth/*：註冊、登入、查詢自己的資料。"""

import jwt
from fastapi.testclient import TestClient


def test_register_success(client: TestClient):
    resp = client.post(
        "/api/auth/register",
        json={"email": "meow@example.com", "password": "password123", "name": "喵星人"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "meow@example.com"
    assert body["name"] == "喵星人"
    assert "id" in body
    assert "created_at" in body
    # 密碼雜湊絕對不能出現在對外的 response 裡
    assert "password" not in body
    assert "password_hash" not in body


def test_register_duplicate_email_returns_409(client: TestClient):
    payload = {"email": "dup@example.com", "password": "password123", "name": "重複貓"}
    first = client.post("/api/auth/register", json=payload)
    assert first.status_code == 201

    second = client.post("/api/auth/register", json=payload)
    assert second.status_code == 409
    assert second.json()["detail"] == "這個 email 已經註冊過了"


def test_register_invalid_password_returns_422(client: TestClient):
    resp = client.post(
        "/api/auth/register",
        json={"email": "short@example.com", "password": "123", "name": "短密碼貓"},
    )
    assert resp.status_code == 422


def test_register_password_over_72_bytes_returns_422(client: TestClient):
    """回歸測試（backend-1）：bcrypt 有 72 bytes 密碼長度上限，超過要在 schema 驗證層
    就被擋成乾淨的 422，不能讓 hash_password() 沒接住的例外一路炸成 500。"""
    resp = client.post(
        "/api/auth/register",
        json={
            "email": "longpw@example.com",
            "password": "a" * 100,  # 100 個 ASCII 字元 = 100 bytes，超過 72 bytes 上限
            "name": "長密碼貓",
        },
    )
    assert resp.status_code == 422
    assert "72" in resp.text  # 錯誤訊息要提到 bcrypt 的 72 bytes 限制，方便學員理解原因


def test_register_invalid_email_returns_422(client: TestClient):
    resp = client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": "password123", "name": "格式錯貓"},
    )
    assert resp.status_code == 422


def test_login_success(client: TestClient):
    client.post(
        "/api/auth/register",
        json={"email": "login@example.com", "password": "password123", "name": "登入貓"},
    )
    resp = client.post(
        "/api/auth/login", json={"email": "login@example.com", "password": "password123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert "access_token" in body and body["access_token"]
    assert body["user"]["email"] == "login@example.com"


def test_login_wrong_password_returns_401(client: TestClient):
    client.post(
        "/api/auth/register",
        json={"email": "wrongpw@example.com", "password": "password123", "name": "錯密碼貓"},
    )
    resp = client.post(
        "/api/auth/login", json={"email": "wrongpw@example.com", "password": "wrong-password"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "email 或密碼錯誤"


def test_login_unknown_email_returns_401(client: TestClient):
    resp = client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "password123"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "email 或密碼錯誤"


def test_me_with_valid_token(client: TestClient, auth_headers: dict):
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "tester@example.com"
    assert "created_at" in body


def test_me_without_token_returns_401(client: TestClient):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "請先登入"


def test_me_with_bad_token_returns_401(client: TestClient):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "請先登入"


def test_me_with_non_numeric_sub_returns_401(client: TestClient):
    """回歸測試（backend-2）：sub 是合法簽章、但內容不是數字字串的 token，
    int(sub) 要被同一個 try/except 接住，回 401「請先登入」，不能變成 500。"""
    # conftest.py 的 db_path fixture 已經把 SECRET_KEY 設成 "test-secret-key"，
    # 這裡用同一把 key、同一種演算法自己簽一個 sub 為非數字字串的偽造 token。
    forged_token = jwt.encode({"sub": "not-a-number"}, "test-secret-key", algorithm="HS256")
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "請先登入"
