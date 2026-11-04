import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_categories_management(client: AsyncClient, register_user):
    # Register & Create Company
    await register_user(
        client,
        {
            "full_name": "Казначей Категорий",
            "email": "cat_user@example.com",
            "password": "Password123!",
        },
    )
    csrf_token = client.cookies["csrf_token"]

    comp_res = await client.post(
        "/api/companies",
        json={"name": "Компания Категорий"},
        headers={"X-CSRF-Token": csrf_token},
    )
    company_id = comp_res.json()["id"]

    # 1. Create Category
    cat_res = await client.post(
        f"/api/companies/{company_id}/categories",
        json={"name": "Аренда"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert cat_res.status_code == 201
    cat_id = cat_res.json()["id"]

    # 2. Case-insensitive duplicate check
    dup_res = await client.post(
        f"/api/companies/{company_id}/categories",
        json={"name": "аренда"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert dup_res.status_code == 409
    assert dup_res.json()["error"]["code"] == "CATEGORY_EXISTS"

    # 3. List Categories
    list_res = await client.get(f"/api/companies/{company_id}/categories")
    assert list_res.status_code == 200
    assert any(c["id"] == cat_id for c in list_res.json())

    # 4. Update Category
    update_res = await client.patch(
        f"/api/companies/{company_id}/categories/{cat_id}",
        json={"name": "Аренда офиса"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Аренда офиса"

    # 5. Delete Category
    del_res = await client.delete(
        f"/api/companies/{company_id}/categories/{cat_id}",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert del_res.status_code == 200

    # 6. Verify deleted
    list_after = await client.get(f"/api/companies/{company_id}/categories")
    assert not any(c["id"] == cat_id for c in list_after.json())
