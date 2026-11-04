import calendar
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_role
from app.crud.analytics import get_category_analytics, get_daily_analytics
from app.dates import get_current_moscow_date
from app.db.connection import get_db
from app.errors import UnprocessableError
from app.models.membership import Membership
from app.schemas.analytics import (
    CategoryAnalyticsResponse,
    DailyAnalyticsResponse,
)

router = APIRouter(prefix="/companies/{company_id}/analytics", tags=["analytics"])


def get_default_period(
    date_from: date | None,
    date_to: date | None,
) -> tuple[date, date]:
    today = get_current_moscow_date()
    if date_from is None and date_to is None:
        first_day = date(today.year, today.month, 1)
        _, last_day_num = calendar.monthrange(today.year, today.month)
        last_day = date(today.year, today.month, last_day_num)
        return first_day, last_day
    if date_from is None:
        assert date_to is not None
        first_day = date(date_to.year, date_to.month, 1)
        return first_day, date_to
    if date_to is None:
        return date_from, today
    return date_from, date_to


@router.get("/daily", response_model=DailyAnalyticsResponse)
async def get_daily(
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
) -> DailyAnalyticsResponse:
    if category_id is not None and uncategorized:
        raise UnprocessableError(
            message="Параметры category_id и uncategorized не могут использоваться одновременно",
            code="INVALID_FILTER",
        )

    start_date, end_date = get_default_period(date_from, date_to)

    if start_date > end_date:
        raise UnprocessableError(
            message="Параметр date_from не может быть позже date_to",
            code="INVALID_DATE_RANGE",
        )

    if (end_date - start_date).days + 1 > 1825:
        raise UnprocessableError(
            message="Период запроса не должен превышать 1825 дней",
            code="PERIOD_TOO_LARGE",
        )

    return await get_daily_analytics(
        session=session,
        company_id=company_id,
        date_from=start_date,
        date_to=end_date,
        direction=direction,
        category_id=category_id,
        uncategorized=uncategorized,
    )


@router.get("/categories", response_model=CategoryAnalyticsResponse)
async def get_categories_summary(
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
) -> CategoryAnalyticsResponse:
    if category_id is not None and uncategorized:
        raise UnprocessableError(
            message="Параметры category_id и uncategorized не могут использоваться одновременно",
            code="INVALID_FILTER",
        )

    start_date, end_date = get_default_period(date_from, date_to)

    if start_date > end_date:
        raise UnprocessableError(
            message="Параметр date_from не может быть позже date_to",
            code="INVALID_DATE_RANGE",
        )

    if (end_date - start_date).days + 1 > 1825:
        raise UnprocessableError(
            message="Период запроса не должен превышать 1825 дней",
            code="PERIOD_TOO_LARGE",
        )

    return await get_category_analytics(
        session=session,
        company_id=company_id,
        date_from=start_date,
        date_to=end_date,
        direction=direction,
        category_id=category_id,
        uncategorized=uncategorized,
    )
