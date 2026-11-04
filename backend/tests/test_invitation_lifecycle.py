import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from app.models.invitation import Invitation
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError


@pytest.fixture
async def invitations(client: AsyncClient, register_user):
    accounts = {}
    for name in ("owner", "recipient", "outsider"):
        client.cookies.clear()
        response = await register_user(
            client,
            {
                "full_name": name,
                "email": f"{name}@example.com",
                "password": "Password123!",
            },
        )
        assert response.status_code == 201
        accounts[name] = dict(client.cookies)

    def login(name):
        client.cookies.clear()
        client.cookies.update(accounts[name])
        return {"X-CSRF-Token": accounts[name]["csrf_token"]}

    headers = login("owner")
    company = await client.post(
        "/api/companies", json={"name": "Lifecycle"}, headers=headers
    )
    assert company.status_code == 201
    base = f"/api/companies/{company.json()['id']}"

    async def create():
        response = await client.post(
            f"{base}/invitations",
            headers=login("owner"),
            json={
                "email": "recipient@example.com",
                "role": "viewer",
            },
        )
        assert response.status_code == 201
        result = response.json()
        assert result["status"] == "pending"
        assert result["created_at"] and result["responded_at"] is None
        return result

    return base, login, create


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action,status", [("accept", "accepted"), ("decline", "declined")]
)
async def test_response_is_terminal_and_preserved(client, invitations, action, status):
    base, login, create = invitations
    invitation = await create()
    response = await client.post(
        f"/api/invitations/{action}",
        headers=login("recipient"),
        json={"token": invitation["token"]},
    )
    assert response.status_code == 200
    companies = (await client.get("/api/companies")).json()
    assert bool(companies) == (action == "accept")
    for next_action in ("accept", "decline"):
        response = await client.post(
            f"/api/invitations/{next_action}",
            headers=login("recipient"),
            json={"token": invitation["token"]},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "INVITATION_CLOSED"
    owner_headers = login("owner")
    path = f"{base}/invitations/{invitation['id']}"
    assert (await client.delete(path, headers=owner_headers)).status_code == 409
    assert (
        await client.post(f"{path}/renew", headers=owner_headers)
    ).status_code == 409
    history = (await client.get(f"{base}/invitations")).json()
    assert len(history) == 1
    assert history[0]["status"] == status
    assert history[0]["responded_at"]
    assert history[0]["token"] is None and history[0]["invite_url"] is None


@pytest.mark.asyncio
async def test_renew_expired_and_revoke_preserve_history(
    client, invitations, db_session
):
    base, login, create = invitations
    old = await create()
    await db_session.execute(
        update(Invitation)
        .where(Invitation.id == old["id"])
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    await db_session.commit()
    history = (await client.get(f"{base}/invitations")).json()
    assert history[0]["status"] == "expired" and history[0]["responded_at"] is None
    for action in ("accept", "decline"):
        response = await client.post(
            f"/api/invitations/{action}",
            headers=login("recipient"),
            json={"token": old["token"]},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVITATION_EXPIRED"
    response = await client.post(
        f"{base}/invitations/{old['id']}/renew", headers=login("owner")
    )
    assert response.status_code == 201
    new = response.json()
    assert new["id"] != old["id"] and new["token"] != old["token"]
    remaining = datetime.fromisoformat(new["expires_at"]) - datetime.now(UTC)
    assert timedelta(hours=47, minutes=59) < remaining <= timedelta(hours=48)
    response = await client.post(
        "/api/invitations/accept",
        headers=login("recipient"),
        json={"token": old["token"]},
    )
    assert response.status_code == 409
    path = f"{base}/invitations/{new['id']}"
    for _ in range(2):
        assert (await client.delete(path, headers=login("owner"))).status_code == 200
    assert (
        await client.post(f"{path}/renew", headers=login("owner"))
    ).status_code == 409
    response = await client.post(
        "/api/invitations/decline",
        headers=login("recipient"),
        json={"token": new["token"]},
    )
    assert response.status_code == 409
    login("owner")
    history = (await client.get(f"{base}/invitations")).json()
    assert len(history) == 2 and all(item["status"] == "revoked" for item in history)
    assert all(item["responded_at"] and item["token"] is None for item in history)


@pytest.mark.asyncio
async def test_invitation_permissions_csrf_and_tenant_scope(client, invitations):
    base, login, create = invitations
    invitation = await create()
    path = f"{base}/invitations/{invitation['id']}"
    for action in ("accept", "decline"):
        response = await client.post(
            f"/api/invitations/{action}",
            headers=login("outsider"),
            json={"token": invitation["token"]},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "EMAIL_MISMATCH"
        login("recipient")
        assert (
            await client.post(
                f"/api/invitations/{action}", json={"token": invitation["token"]}
            )
        ).status_code == 403
        client.cookies.clear()
        assert (
            await client.post(
                f"/api/invitations/{action}", json={"token": invitation["token"]}
            )
        ).status_code == 401
    login("owner")
    assert (await client.post(f"{path}/renew")).status_code == 403
    assert (await client.delete(path)).status_code == 403
    assert (
        await client.post(f"{base}/invitations/999999/renew", headers=login("owner"))
    ).status_code == 404
    company = await client.post(
        "/api/companies", headers=login("outsider"), json={"name": "Other"}
    )
    foreign_path = (
        f"/api/companies/{company.json()['id']}/invitations/{invitation['id']}"
    )
    assert (
        await client.post(f"{foreign_path}/renew", headers=login("outsider"))
    ).status_code == 404
    assert (
        await client.delete(foreign_path, headers=login("outsider"))
    ).status_code == 404
    assert (await client.get(f"{base}/invitations")).status_code == 404
    assert (
        await client.post(f"{path}/renew", headers=login("outsider"))
    ).status_code == 404
    assert (
        await client.post(
            "/api/invitations/accept",
            headers=login("recipient"),
            json={"token": invitation["token"]},
        )
    ).status_code == 200
    assert (
        await client.post(f"{path}/renew", headers=login("recipient"))
    ).status_code == 403
    assert (await client.delete(path, headers=login("recipient"))).status_code == 403
    assert (await client.get(f"{base}/invitations")).status_code == 403


@pytest.mark.asyncio
async def test_concurrent_accept_has_single_outcome(client, invitations):
    base, login, create = invitations
    invitation = await create()
    headers = login("recipient")
    responses = await asyncio.gather(
        *[
            client.post(
                "/api/invitations/accept",
                headers=headers,
                json={"token": invitation["token"]},
            )
            for _ in range(2)
        ]
    )
    assert sorted(response.status_code for response in responses) == [200, 409]
    assert len((await client.get(f"{base}/members")).json()) == 2


@pytest.mark.asyncio
async def test_invitation_status_timestamp_constraint(client, invitations, db_session):
    _, _, create = invitations
    invitation = await create()
    with pytest.raises(IntegrityError):
        await db_session.execute(
            update(Invitation)
            .where(Invitation.id == invitation["id"])
            .values(status="accepted")
        )
    await db_session.rollback()
    row = await db_session.scalar(
        select(Invitation).where(Invitation.id == invitation["id"])
    )
    assert row.status == "pending" and row.responded_at is None
