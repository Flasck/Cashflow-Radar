import io

import openpyxl
from fastapi import APIRouter, Response

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("/transactions.xlsx")
async def get_transactions_xlsx_template() -> Response:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "transactions"
    ws.append(["date", "amount", "direction", "category", "purpose"])
    ws.append(["2026-10-01", "100000.00", "inflow", "Продажи", "Оплата заказа"])
    ws.append(["2026-10-02", "-15000.00", "", "Аренда", "Склад"])
    ws.append(["2026-10-03", "2500.00", "outflow", "Расходные материалы", ""])
    output = io.BytesIO()
    wb.save(output)
    wb.close()
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="transactions.xlsx"'},
    )


@router.get("/transactions.csv")
async def get_transactions_csv_template() -> Response:
    csv_content = (
        "date,amount,direction,category,purpose\n"
        "2026-10-01,100000.00,inflow,Продажи,Оплата заказа\n"
        "2026-10-02,-15000.00,,Аренда,Склад\n"
        "2026-10-03,2500.00,outflow,Расходные материалы,\n"
    )
    return Response(
        content=csv_content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="transactions.csv"'},
    )
