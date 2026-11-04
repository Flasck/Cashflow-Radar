import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_register_and_login_flow(client: AsyncClient, mail_outbox):
    # 1. Register
    reg_payload = {
        "full_name": "Тестовый Пользователь",
        "email": "user@example.com",
        "password": "StrongPassword123!",
    }
    reg_res = await client.post("/api/auth/register", json=reg_payload)
    assert reg_res.status_code == 201
    reg_data = reg_res.json()
    assert reg_data["email"] == "user@example.com"
    assert reg_data["status"] == "verification_required"
    assert "access_token" not in client.cookies
    assert (await client.get("/api/auth/me")).status_code == 401
    unverified_login = await client.post(
        "/api/auth/login",
        json={"email": reg_payload["email"], "password": reg_payload["password"]},
    )
    assert unverified_login.status_code == 403
    assert unverified_login.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"
    verified = await client.post(
        "/api/auth/verify-email",
        json={"email": reg_payload["email"], "code": mail_outbox[reg_payload["email"]]},
    )
    assert verified.status_code == 200
    assert verified.json()["full_name"] == "Тестовый Пользователь"
    assert "access_token" in client.cookies
    assert "csrf_token" in client.cookies
    csrf_token = client.cookies["csrf_token"]

    # 2. Get Me
    me_res = await client.get("/api/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "user@example.com"

    # 3. Duplicate email conflict
    dup_res = await client.post("/api/auth/register", json=reg_payload)
    assert dup_res.status_code == 409
    assert dup_res.json()["error"]["code"] == "EMAIL_EXISTS"

    # 4. Logout
    logout_res = await client.post(
        "/api/auth/logout",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert logout_res.status_code == 200

    # 5. Get Me after logout should fail (401)
    client.cookies.clear()
    unauth_res = await client.get("/api/auth/me")
    assert unauth_res.status_code == 401

    # 6. Login
    login_payload = {
        "email": "user@example.com",
        "password": "StrongPassword123!",
    }
    login_res = await client.post("/api/auth/login", json=login_payload)
    assert login_res.status_code == 200
    assert login_res.json()["email"] == "user@example.com"
    assert "access_token" in client.cookies

    # 7. Invalid login
    bad_login_res = await client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "WrongPassword!"},
    )
    assert bad_login_res.status_code == 401
    assert bad_login_res.json()["error"]["code"] == "INVALID_CREDENTIALS"
