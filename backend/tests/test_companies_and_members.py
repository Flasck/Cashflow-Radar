import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_company_and_invitation_flow(client: AsyncClient, register_user):
    # Register Owner
    await register_user(
        client,
        {
            "full_name": "Владелец",
            "email": "owner@example.com",
            "password": "Password123!",
        },
    )
    csrf_token = client.cookies["csrf_token"]

    # Create Company
    company_res = await client.post(
        "/api/companies",
        json={"name": "ООО Ромашка", "industry_code": "RETAIL"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert company_res.status_code == 201
    comp_data = company_res.json()
    company_id = comp_data["id"]
    assert comp_data["name"] == "ООО Ромашка"
    assert comp_data["role"] == "owner"

    # List Companies
    list_res = await client.get("/api/companies")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # Check Members (verifies MemberResponse including company_id)
    members_res = await client.get(f"/api/companies/{company_id}/members")
    assert members_res.status_code == 200
    members = members_res.json()
    assert len(members) == 1
    assert members[0]["company_id"] == company_id
    assert members[0]["role"] == "owner"

    # Create Invitation for treasurer
    inv_res = await client.post(
        f"/api/companies/{company_id}/invitations",
        json={"email": "treasurer@example.com", "role": "treasurer"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert inv_res.status_code == 201
    inv_data = inv_res.json()
    invite_token = inv_data["token"]
    assert invite_token is not None
    assert inv_data["invite_url"] is not None

    # Switch user: Register invited user
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf_token})
    client.cookies.clear()

    await register_user(
        client,
        {
            "full_name": "Казначей",
            "email": "treasurer@example.com",
            "password": "Password123!",
        },
    )
    treasurer_csrf = client.cookies["csrf_token"]

    # Accept invitation
    accept_res = await client.post(
        "/api/invitations/accept",
        json={"token": invite_token},
        headers={"X-CSRF-Token": treasurer_csrf},
    )
    assert accept_res.status_code == 200
    assert accept_res.json()["role"] == "treasurer"

    # Verify company is now in treasurer's list
    treasurer_comps = await client.get("/api/companies")
    assert treasurer_comps.status_code == 200
    assert any(
        c["id"] == company_id and c["role"] == "treasurer"
        for c in treasurer_comps.json()
    )

    # Verify members list now has 2 members
    members_after = await client.get(f"/api/companies/{company_id}/members")
    assert members_after.status_code == 200
    assert len(members_after.json()) == 2

    # Switch back to owner to test company update
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": treasurer_csrf})
    client.cookies.clear()
    await client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "Password123!"},
    )
    owner_csrf = client.cookies["csrf_token"]

    # Reject name: null
    bad_upd = await client.patch(
        f"/api/companies/{company_id}",
        json={"name": None},
        headers={"X-CSRF-Token": owner_csrf},
    )
    assert bad_upd.status_code == 422

    # Clearing industry_code via null
    clear_ind = await client.patch(
        f"/api/companies/{company_id}",
        json={"industry_code": None},
        headers={"X-CSRF-Token": owner_csrf},
    )
    assert clear_ind.status_code == 200
    assert clear_ind.json()["industry_code"] is None

    # Treasurer attempts to invite another person (should fail with 403 Forbidden)
    # Log back in as treasurer
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": owner_csrf})
    client.cookies.clear()
    await client.post(
        "/api/auth/login",
        json={"email": "treasurer@example.com", "password": "Password123!"},
    )
    treasurer_csrf_2 = client.cookies["csrf_token"]

    forbidden_invite = await client.post(
        f"/api/companies/{company_id}/invitations",
        json={"email": "other@example.com", "role": "viewer"},
        headers={"X-CSRF-Token": treasurer_csrf_2},
    )
    assert forbidden_invite.status_code == 403
