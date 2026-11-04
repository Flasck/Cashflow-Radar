import io
from typing import Annotated, Literal

import openpyxl
from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    require_csrf,
    require_role,
)
from app.db.connection import get_db
from app.errors import PayloadTooLargeError, UnsupportedMediaTypeError
from app.importing import MAX_FILE_SIZE, commit_import, preview_import
from app.models.membership import Membership
from app.schemas.imports import (
    CommitRequest,
    CommitResponse,
    PreviewResponse,
)

router = APIRouter(prefix="/companies/{company_id}/imports", tags=["imports"])


@router.post("/preview", response_model=PreviewResponse)
async def preview_file_import(
    company_id: int,
    file: Annotated[UploadFile, File()],
    _membership: Annotated[Membership, Depends(require_role("owner", "treasurer"))],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> PreviewResponse:
    filename = file.filename or "import.csv"
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise PayloadTooLargeError("Размер файла превышает допустимый лимит 5 МБ")

    try:
        return await preview_import(
            session=session,
            company_id=company_id,
            filename=filename,
            content_bytes=content,
        )
    finally:
        await file.close()


@router.post(
    "/commit", response_model=CommitResponse, status_code=status.HTTP_201_CREATED
)
async def commit_file_import(
    company_id: int,
    payload: CommitRequest,
    _membership: Annotated[Membership, Depends(require_role("owner", "treasurer"))],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> CommitResponse:
    result = await commit_import(
        session=session,
        company_id=company_id,
        request=payload,
    )

    return result


@router.get("/template")
async def download_import_template(
    company_id: int,
    _membership: Annotated[
        Membership, Depends(require_role("owner", "treasurer", "viewer"))
    ],
    format: Annotated[Literal["csv", "xlsx"], Query()] = "csv",
) -> Response:
    if format == "csv":
        csv_content = (
            "date,amount,direction,category,purpose\n"
            "2026-10-01,100000.00,inflow,Продажи,Оплата заказа\n"
            "2026-10-02,-15000.00,,Аренда,Склад\n"
            "2026-10-03,2500.00,outflow,Расходные материалы,\n"
        )
        return Response(
            content=csv_content.encode("utf-8-sig"),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="transactions_template.csv"'
            },
        )
    elif format == "xlsx":
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
            headers={
                "Content-Disposition": 'attachment; filename="transactions_template.xlsx"'
            },
        )
    else:
        raise UnsupportedMediaTypeError("Поддерживаются форматы только csv или xlsx")
