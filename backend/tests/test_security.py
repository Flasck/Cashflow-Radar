import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_origin_and_csrf_protection(client: AsyncClient, register_user):
    # 0. Missing Origin header on mutation
    no_origin_client = AsyncClient(
        transport=client._transport,
        base_url=str(client.base_url),
    )
    no_origin_res = await no_origin_client.post(
        "/api/auth/register",
        json={
            "full_name": "Без Origin",
            "email": "no_origin@example.com",
            "password": "Password123!",
        },
    )
    assert no_origin_res.status_code == 403
    assert no_origin_res.json()["error"]["code"] == "MISSING_ORIGIN"

    # 1. Invalid Origin on register
    bad_origin_res = await client.post(
        "/api/auth/register",
        json={
            "full_name": "Хакер",
            "email": "hacker@evil.com",
            "password": "Password123!",
        },
        headers={"Origin": "http://evil.com"},
    )
    assert bad_origin_res.status_code == 403
    assert bad_origin_res.json()["error"]["code"] == "INVALID_ORIGIN"

    # 2. Register with valid origin
    reg_res = await register_user(
        client,
        {
            "full_name": "Безопасный",
            "email": "sec@example.com",
            "password": "Password123!",
        },
    )
    assert reg_res.status_code == 201
    assert client.cookies["csrf_token"]

    # 3. Missing X-CSRF-Token on mutating action
    comp_missing_csrf = await client.post(
        "/api/companies",
        json={"name": "Компания Без CSRF"},
    )
    assert comp_missing_csrf.status_code == 403
    assert comp_missing_csrf.json()["error"]["code"] == "INVALID_CSRF"

    # 4. Wrong X-CSRF-Token
    comp_bad_csrf = await client.post(
        "/api/companies",
        json={"name": "Компания с плохим CSRF"},
        headers={"X-CSRF-Token": "wrong-csrf-token"},
    )
    assert comp_bad_csrf.status_code == 403
    assert comp_bad_csrf.json()["error"]["code"] == "INVALID_CSRF"

    # 5. Validation error does not echo sensitive password input
    short_pwd_res = await client.post(
        "/api/auth/register",
        json={
            "full_name": "Короткий",
            "email": "short@example.com",
            "password": "short",
        },
    )
    assert short_pwd_res.status_code == 422
    err_json = short_pwd_res.json()["error"]
    assert "password" in err_json["fields"]
    # Check that literal "short" is not leaked in error response
    assert "short" not in err_json["fields"]["password"]


@pytest.mark.asyncio
async def test_payload_size_limit(client: AsyncClient):
    huge_headers = {
        "Content-Length": str(10 * 1024 * 1024),  # 10 MB
    }
    res = await client.post(
        "/api/auth/register",
        headers=huge_headers,
    )
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"

    # Raw chunked stream exceeding 5 MiB without Content-Length header
    async def chunk_generator():
        chunk = b"x" * (1024 * 1024)  # 1 MiB chunk
        for _ in range(6):  # 6 MiB total
            yield chunk

    chunked_res = await client.post(
        "/api/auth/register",
        content=chunk_generator(),
        headers={"Origin": "http://localhost:3000", "Content-Type": "application/json"},
    )
    assert chunked_res.status_code == 413
    assert chunked_res.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
