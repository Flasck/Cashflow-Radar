import io

import openpyxl
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_import_preview_and_commit(client: AsyncClient, register_user):
    # Register & Create Company
    await register_user(
        client,
        {
            "full_name": "Импортер",
            "email": "importer@example.com",
            "password": "Password123!",
        },
    )
    csrf_token = client.cookies["csrf_token"]

    comp_res = await client.post(
        "/api/companies",
        json={"name": "Компания Импорта"},
        headers={"X-CSRF-Token": csrf_token},
    )
    company_id = comp_res.json()["id"]

    # 1. Preview CSV (requires CSRF)
    csv_data = (
        "date,amount,direction,category,purpose\n"
        "2026-10-01,100000.00,inflow,Выручка,Оплата заказа\n"
        "2026-10-02,-15000.00,,Аренда,Офис\n"
        "2026-10-03,2500.00,outflow,Канцтовары,\n"
    ).encode()

    files = {"file": ("test.csv", csv_data, "text/csv")}
    preview_res = await client.post(
        f"/api/companies/{company_id}/imports/preview",
        files=files,
        headers={"X-CSRF-Token": csrf_token},
    )
    assert preview_res.status_code == 200
    pdata = preview_res.json()
    assert pdata["can_commit"] is True
    assert pdata["summary"]["total_rows"] == 3
    assert pdata["summary"]["valid_rows"] == 3
    assert pdata["summary"]["total_net"] == "82500.00"
    assert pdata["rows"][0]["is_valid"] is True
    assert len(pdata["new_categories"]) == 3
    assert "Выручка" in pdata["new_categories"]

    # 2. Commit CSV rows
    commit_payload = {
        "rows": [
            {
                "operation_date": "2026-10-01",
                "amount": "100000.00",
                "direction": "inflow",
                "category": "Выручка",
                "purpose": "Оплата заказа",
            },
            {
                "operation_date": "2026-10-02",
                "amount": "15000.00",
                "direction": "outflow",
                "category": "Аренда",
                "purpose": "Офис",
            },
            {
                "operation_date": "2026-10-03",
                "amount": "2500.00",
                "direction": "outflow",
                "category": "Канцтовары",
                "purpose": None,
            },
        ]
    }
    commit_res = await client.post(
        f"/api/companies/{company_id}/imports/commit",
        json=commit_payload,
        headers={"X-CSRF-Token": csrf_token},
    )
    assert commit_res.status_code == 201
    cdata = commit_res.json()
    assert cdata["imported_count"] == 3
    assert cdata["created_categories_count"] == 3

    # 3. Check transactions list
    tx_list = await client.get(f"/api/companies/{company_id}/transactions")
    assert tx_list.status_code == 200
    assert tx_list.json()["total"] == 3

    # 4. Check categories list
    cat_list = await client.get(f"/api/companies/{company_id}/categories")
    assert cat_list.status_code == 200
    assert len(cat_list.json()) == 3

    # 5. Preview invalid CSV with invalid direction, date, and conflict
    bad_csv = (
        "date,amount,direction,category,purpose\n"
        "not-a-date,-100.00,inflow,Тест,Несоответствие\n"
        "2026-10-01,50.00,bogus_direction,,Неверное направление\n"
        "2099-01-01,100.00,inflow,Будущее,Будущая дата\n"
    ).encode()
    bad_preview = await client.post(
        f"/api/companies/{company_id}/imports/preview",
        files={"file": ("bad.csv", bad_csv, "text/csv")},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert bad_preview.status_code == 200
    bad_data = bad_preview.json()
    assert bad_data["can_commit"] is False
    assert bad_data["summary"]["error_rows"] == 3
    assert bad_data["rows"][0]["is_valid"] is False
    assert bad_data["rows"][1]["is_valid"] is False
    assert bad_data["rows"][2]["is_valid"] is False
    assert len(bad_data["errors"]) >= 3

    # 6. Test XLSX preview
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "transactions"
    ws.append(["date", "amount", "direction", "category", "purpose"])
    ws.append(["2026-10-04", "5000.00", "inflow", "Консалтинг", "Анализ"])
    xlsx_buf = io.BytesIO()
    wb.save(xlsx_buf)
    wb.close()

    xlsx_res = await client.post(
        f"/api/companies/{company_id}/imports/preview",
        files={
            "file": (
                "test.xlsx",
                xlsx_buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert xlsx_res.status_code == 200
    xdata = xlsx_res.json()
    assert xdata["can_commit"] is True
    assert xdata["summary"]["valid_rows"] == 1
    assert "Консалтинг" in xdata["new_categories"]

    # 7. Test XLSX with formula (should be rejected in preview)
    wb_form = openpyxl.Workbook()
    ws_form = wb_form.active
    ws_form.title = "transactions"
    ws_form.append(["date", "amount", "direction", "category", "purpose"])
    ws_form.append(["2026-10-04", "=100+200", "inflow", "Прочее", "Формула"])
    form_buf = io.BytesIO()
    wb_form.save(form_buf)
    wb_form.close()

    form_res = await client.post(
        f"/api/companies/{company_id}/imports/preview",
        files={
            "file": (
                "formula.xlsx",
                form_buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert form_res.status_code == 200
    fdata = form_res.json()
    assert fdata["can_commit"] is False
    assert fdata["rows"][0]["is_valid"] is False
    assert any("формул" in e.lower() for e in fdata["rows"][0]["errors"])

    # 8. Test XLSX with gap in headers
    wb_gap = openpyxl.Workbook()
    ws_gap = wb_gap.active
    ws_gap.title = "transactions"
    ws_gap.append(["date", None, "amount", "direction", "category", "purpose"])
    ws_gap.append(["2026-10-04", "extra", "100.00", "inflow", "Прочее", "Сдвиг"])
    gap_buf = io.BytesIO()
    wb_gap.save(gap_buf)
    wb_gap.close()

    gap_res = await client.post(
        f"/api/companies/{company_id}/imports/preview",
        files={
            "file": (
                "gap.xlsx",
                gap_buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert gap_res.status_code == 422
    assert "без заголовка" in gap_res.json()["error"]["message"]

    # 9. Test XLSX with too many columns (> 10)
    wb_wide = openpyxl.Workbook()
    ws_wide = wb_wide.active
    ws_wide.title = "transactions"
    headers_wide = ["date", "amount", "direction", "category", "purpose"] + [
        f"extra_{i}" for i in range(6)
    ]
    ws_wide.append(headers_wide)
    wide_buf = io.BytesIO()
    wb_wide.save(wide_buf)
    wb_wide.close()

    wide_res = await client.post(
        f"/api/companies/{company_id}/imports/preview",
        files={
            "file": (
                "wide.xlsx",
                wide_buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert wide_res.status_code == 422
    assert "максимум 10" in wide_res.json()["error"]["message"]

    # 10. Test CSV edge money amounts (NaN, Infinity, 1e2)
    csv_edge = (
        "date,amount,direction,category,purpose\n"
        "2026-10-04,NaN,inflow,Прочее,Тест NaN\n"
        "2026-10-04,Infinity,inflow,Прочее,Тест Infinity\n"
        "2026-10-04,1e2,inflow,Прочее,Тест 1e2\n"
    )
    edge_res = await client.post(
        f"/api/companies/{company_id}/imports/preview",
        files={"file": ("edge.csv", csv_edge.encode("utf-8"), "text/csv")},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert edge_res.status_code == 200
    edge_data = edge_res.json()
    assert edge_data["can_commit"] is False
    assert edge_data["summary"]["error_rows"] == 3
    # Ensure invalid money does not output "NaN" or "Infinity", outputs null
    for row in edge_data["rows"]:
        assert row["is_valid"] is False
        assert row["amount"] is None

    # 11. Test XLSX excess precision (1.234) and date with time rejection
    wb_num = openpyxl.Workbook()
    ws_num = wb_num.active
    ws_num.title = "transactions"
    ws_num.append(["date", "amount", "direction", "category", "purpose"])
    ws_num.append(["2026-10-04", 1.234, "inflow", "Прочее", "Excess precision"])
    ws_num.append(["2026-10-04 12:30:00", 100.0, "inflow", "Прочее", "Date with time"])
    num_buf = io.BytesIO()
    wb_num.save(num_buf)
    wb_num.close()

    num_res = await client.post(
        f"/api/companies/{company_id}/imports/preview",
        files={
            "file": (
                "num.xlsx",
                num_buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert num_res.status_code == 200
    ndata = num_res.json()
    assert ndata["can_commit"] is False
    assert ndata["rows"][0]["is_valid"] is False
    assert ndata["rows"][0]["amount"] is None
    assert any("двух знаков" in e for e in ndata["rows"][0]["errors"])
    assert ndata["rows"][1]["is_valid"] is False
    assert any("формат даты" in e.lower() for e in ndata["rows"][1]["errors"])

    # 12. Template route check
    template_res = await client.get("/api/templates/transactions.xlsx")
    assert template_res.status_code == 200
    assert (
        template_res.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
