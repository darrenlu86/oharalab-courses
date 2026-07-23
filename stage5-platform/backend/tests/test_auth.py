"""測試 /api/auth/*：註冊、登入、查詢自己的資料。"""

from fastapi.testclient import TestClient


def test_register_success(client: TestClient):
    resp = client.post(
        "/api/auth/register",
        json={"email": "neo@example.com", "password": "password123", "name": "王小明"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "neo@example.com"
    assert body["name"] == "王小明"
    assert "id" in body
    assert "created_at" in body
    assert "password" not in body
    assert "password_hash" not in body


def test_register_duplicate_email_returns_409(client: TestClient):
    payload = {"email": "dup@example.com", "password": "password123", "name": "重複的人"}
    client.post("/api/auth/register", json=payload)
    resp = client.post("/api/auth/register", json=payload)
    assert resp.status_code == 409
    assert resp.json()["detail"] == "這個 email 已經註冊過了"


def test_register_password_too_short_returns_422(client: TestClient):
    resp = client.post(
        "/api/auth/register",
        json={"email": "short@example.com", "password": "1234567", "name": "密碼太短"},
    )
    assert resp.status_code == 422


def test_login_success(client: TestClient):
    client.post(
        "/api/auth/register",
        json={"email": "login@example.com", "password": "password123", "name": "登入測試"},
    )
    resp = client.post(
        "/api/auth/login", json={"email": "login@example.com", "password": "password123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "login@example.com"


def test_login_wrong_password_returns_401(client: TestClient):
    client.post(
        "/api/auth/register",
        json={"email": "wrongpw@example.com", "password": "password123", "name": "測試"},
    )
    resp = client.post(
        "/api/auth/login", json={"email": "wrongpw@example.com", "password": "wrongpassword"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "email 或密碼錯誤"


def test_login_unknown_email_returns_401(client: TestClient):
    resp = client.post(
        "/api/auth/login", json={"email": "notexist@example.com", "password": "password123"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "email 或密碼錯誤"


def test_me_with_valid_token(client: TestClient, auth_headers: dict):
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "tester@example.com"


def test_me_without_token_returns_401(client: TestClient):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "請先登入"


def test_me_with_bad_token_returns_401(client: TestClient):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "請先登入"
