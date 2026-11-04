from datetime import date, timedelta

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_transactions_crud_and_analytics(client: AsyncClient, register_user):
    # Register & Create Company
    await register_user(
        client,
        {
            "full_name": "Аналитик",
            "email": "analyst@example.com",
            "password": "Password123!",
        },
    )
    csrf_token = client.cookies["csrf_token"]

    comp_res = await client.post(
        "/api/companies",
        json={"name": "Аналитическая Компания"},
        headers={"X-CSRF-Token": csrf_token},
    )
    company_id = comp_res.json()["id"]

    # Create Category
    cat_res = await client.post(
        f"/api/companies/{company_id}/categories",
        json={"name": "Продажи"},
        headers={"X-CSRF-Token": csrf_token},
    )
    cat_id = cat_res.json()["id"]

    # 1. Reject future date
    future_date = (date.today() + timedelta(days=2)).isoformat()
    future_res = await client.post(
        f"/api/companies/{company_id}/transactions",
        json={
            "operation_date": future_date,
            "amount": "1000.00",
            "direction": "inflow",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert future_res.status_code == 422
    assert future_res.json()["error"]["code"] == "FUTURE_DATE_NOT_ALLOWED"

    # 2. Create valid transactions
    t1_date = (date.today() - timedelta(days=3)).isoformat()
    t2_date = (date.today() - timedelta(days=1)).isoformat()

    tx1_res = await client.post(
        f"/api/companies/{company_id}/transactions",
        json={
            "operation_date": t1_date,
            "amount": "15000.50",
            "direction": "inflow",
            "category_id": cat_id,
            "purpose": "Оплата счета №1",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert tx1_res.status_code == 201
    tx1_data = tx1_res.json()
    assert tx1_data["amount"] == "15000.50"
    assert tx1_data["direction"] == "inflow"

    tx2_res = await client.post(
        f"/api/companies/{company_id}/transactions",
        json={
            "operation_date": t2_date,
            "amount": "5000.00",
            "direction": "outflow",
            "category_id": None,
            "purpose": "Без категории",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert tx2_res.status_code == 201

    # 3. List transactions
    list_res = await client.get(
        f"/api/companies/{company_id}/transactions?page=1&page_size=10"
    )
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] == 2
    assert len(list_data["items"]) == 2

    # 4. Filter by uncategorized
    uncat_res = await client.get(
        f"/api/companies/{company_id}/transactions?uncategorized=true"
    )
    assert uncat_res.status_code == 200
    assert uncat_res.json()["total"] == 1
    assert uncat_res.json()["items"][0]["category_id"] is None

    # 5. Daily analytics: verifies dense series and missing zero days
    daily_res = await client.get(
        f"/api/companies/{company_id}/analytics/daily?date_from={t1_date}&date_to={t2_date}"
    )
    assert daily_res.status_code == 200
    daily_data = daily_res.json()
    assert len(daily_data["items"]) == 3  # t1_date, middle day (zeros), t2_date
    assert daily_data["totals"]["inflow"] == "15000.50"
    assert daily_data["totals"]["outflow"] == "5000.00"
    assert daily_data["totals"]["net_cash_flow"] == "10000.50"

    # 6. Categories analytics
    cat_analytics_res = await client.get(
        f"/api/companies/{company_id}/analytics/categories?date_from={t1_date}&date_to={t2_date}"
    )
    assert cat_analytics_res.status_code == 200
    cat_items = cat_analytics_res.json()["items"]
    assert len(cat_items) == 2
    sales_item = next(item for item in cat_items if item["category_id"] == cat_id)
    assert sales_item["inflow"] == "15000.50"
    none_item = next(item for item in cat_items if item["category_id"] is None)
    assert none_item["category_name"] == "Без категории"
    assert none_item["outflow"] == "5000.00"

    # 7. Categories analytics with filters
    cat_filtered_res = await client.get(
        f"/api/companies/{company_id}/analytics/categories?date_from={t1_date}&date_to={t2_date}&direction=inflow"
    )
    assert cat_filtered_res.status_code == 200
    cat_filtered_items = cat_filtered_res.json()["items"]
    # Only items that have inflow or all categories with matching conditions
    sales_filtered = next(
        item for item in cat_filtered_items if item["category_id"] == cat_id
    )
    assert sales_filtered["inflow"] == "15000.50"

    # Mutual exclusion check on categories analytics
    mutual_res = await client.get(
        f"/api/companies/{company_id}/analytics/categories?category_id={cat_id}&uncategorized=true"
    )
    assert mutual_res.status_code == 422
    assert mutual_res.json()["error"]["code"] == "INVALID_FILTER"

    # 8. Test transaction update rejecting null amount
    tx1_id = tx1_data["id"]
    bad_tx_upd = await client.patch(
        f"/api/companies/{company_id}/transactions/{tx1_id}",
        json={"amount": None},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert bad_tx_upd.status_code == 422

    # 9. Category in-use restriction check
    del_cat_res = await client.delete(
        f"/api/companies/{company_id}/categories/{cat_id}",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert del_cat_res.status_code == 409
    assert del_cat_res.json()["error"]["code"] == "CATEGORY_IN_USE"

    # 10. Delete transaction, then delete category
    del_tx_res = await client.delete(
        f"/api/companies/{company_id}/transactions/{tx1_id}",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert del_tx_res.status_code == 200

    del_cat_ok = await client.delete(
        f"/api/companies/{company_id}/categories/{cat_id}",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert del_cat_ok.status_code == 200
