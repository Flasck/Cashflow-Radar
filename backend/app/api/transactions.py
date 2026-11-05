from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    require_csrf,
    require_role,
)
from app.crud.categories import get_category
from app.crud.transactions import (
    create_transaction,
    delete_transaction,
    get_transaction,
    get_transaction_with_category,
    list_transactions,
)
from app.dates import get_current_moscow_date
from app.db.connection import get_db
from app.errors import NotFoundError, UnprocessableError
from app.models.membership import Membership
from app.schemas.common import format_decimal
from app.schemas.transactions import (
    TransactionCreate,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdate,
)

router = APIRouter(prefix="/companies/{company_id}/transactions", tags=["transactions"])


def _format_tx_response(tx, cat_name: str | None = None) -> TransactionResponse:
    return TransactionResponse(
        id=tx.id,
        company_id=tx.company_id,
        operation_date=tx.operation_date.isoformat(),
        amount=format_decimal(tx.amount),
        direction=tx.direction,
        category_id=tx.category_id,
        category_name=cat_name,
        purpose=tx.purpose,
    )


@router.get("", response_model=TransactionListResponse)
async def get_transactions(
    company_id: int,
    _membership: Annotated[
        Membership, Depends(require_role("owner", "treasurer", "viewer"))
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
    date_from: date | None = None,
    date_to: date | None = None,
    direction: Literal["inflow", "outflow"] | None = None,
    category_id: int | None = None,
    uncategorized: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> TransactionListResponse:
    if category_id is not None and uncategorized:
        raise UnprocessableError(
            message="Параметры category_id и uncategorized не могут использоваться одновременно",
            code="INVALID_FILTER",
        )

    if date_from is not None and date_to is not None and date_from > date_to:
        raise UnprocessableError(
            message="Параметр date_from не может быть позже date_to",
            code="INVALID_DATE_RANGE",
        )

    items, total = await list_transactions(
        session=session,
        company_id=company_id,
        date_from=date_from,
        date_to=date_to,
        direction=direction,
        category_id=category_id,
        uncategorized=uncategorized,
        page=page,
        page_size=page_size,
    )

    result_items = [_format_tx_response(tx, cat_name) for tx, cat_name in items]
    return TransactionListResponse(
        items=result_items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED
)
async def add_transaction(
    company_id: int,
    payload: TransactionCreate,
    _membership: Annotated[Membership, Depends(require_role("owner", "treasurer"))],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> TransactionResponse:
    today_msk = get_current_moscow_date()
    if payload.operation_date > today_msk:
        raise UnprocessableError(
            message=f"Дата операции не может быть в будущем (текущая дата: {today_msk.isoformat()})",
            code="FUTURE_DATE_NOT_ALLOWED",
        )

    cat_name = None
    if payload.category_id is not None:
        cat = await get_category(session, company_id, payload.category_id)
        if cat is None:
            raise UnprocessableError(
                message="Указанная категория не найдена в данной компании",
                code="CATEGORY_NOT_FOUND",
            )
        cat_name = cat.name

    tx = await create_transaction(
        session=session,
        company_id=company_id,
        operation_date=payload.operation_date,
        amount=payload.amount,
        direction=payload.direction,
        category_id=payload.category_id,
        purpose=payload.purpose,
    )
    await session.commit()

    return _format_tx_response(tx, cat_name)


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction_details(
    company_id: int,
    transaction_id: int,
    _membership: Annotated[
        Membership, Depends(require_role("owner", "treasurer", "viewer"))
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TransactionResponse:
    row = await get_transaction_with_category(session, company_id, transaction_id)
    if row is None:
        raise NotFoundError(message="Операция не найдена", code="TRANSACTION_NOT_FOUND")

    tx, cat_name = row
    return _format_tx_response(tx, cat_name)


@router.patch("/{transaction_id}", response_model=TransactionResponse)
async def edit_transaction(
    company_id: int,
    transaction_id: int,
    payload: TransactionUpdate,
    _membership: Annotated[Membership, Depends(require_role("owner", "treasurer"))],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> TransactionResponse:
    existing = await get_transaction(session, company_id, transaction_id)
    if existing is None:
        raise NotFoundError(message="Операция не найдена", code="TRANSACTION_NOT_FOUND")

    today_msk = get_current_moscow_date()
    if payload.operation_date is not None and payload.operation_date > today_msk:
        raise UnprocessableError(
            message=f"Дата операции не может быть в будущем (текущая дата: {today_msk.isoformat()})",
            code="FUTURE_DATE_NOT_ALLOWED",
        )

    category_id = (
        payload.category_id
        if "category_id" in payload.model_fields_set
        else existing.category_id
    )
    cat_name = None
    if category_id is not None:
        category = await get_category(session, company_id, category_id)
        if category is None:
            raise UnprocessableError(
                message="Указанная категория не найдена в данной компании",
                code="CATEGORY_NOT_FOUND",
            )
        cat_name = category.name

    for field in payload.model_fields_set:
        setattr(existing, field, getattr(payload, field))
    await session.commit()

    return _format_tx_response(existing, cat_name)


@router.delete("/{transaction_id}")
async def remove_transaction(
    company_id: int,
    transaction_id: int,
    _membership: Annotated[Membership, Depends(require_role("owner", "treasurer"))],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, str]:
    deleted = await delete_transaction(session, company_id, transaction_id)
    if not deleted:
        raise NotFoundError(message="Операция не найдена", code="TRANSACTION_NOT_FOUND")

    await session.commit()

    return {"status": "ok"}
