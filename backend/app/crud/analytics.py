from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.transaction import Transaction
from app.schemas.analytics import (
    CategoryAnalyticsItem,
    CategoryAnalyticsResponse,
    DailyAnalyticsItem,
    DailyAnalyticsResponse,
    DailyAnalyticsTotals,
)
from app.schemas.common import format_decimal


async def get_daily_analytics(
    session: AsyncSession,
    company_id: int,
    date_from: date,
    date_to: date,
    direction: str | None = None,
    category_id: int | None = None,
    uncategorized: bool = False,
) -> DailyAnalyticsResponse:
    base_conditions = [
        Transaction.company_id == company_id,
        Transaction.operation_date >= date_from,
        Transaction.operation_date <= date_to,
    ]

    if direction is not None:
        base_conditions.append(Transaction.direction == direction)
    if uncategorized:
        base_conditions.append(Transaction.category_id.is_(None))
    elif category_id is not None:
        base_conditions.append(Transaction.category_id == category_id)

    inflow_sum = func.coalesce(
        func.sum(
            case(
                (Transaction.direction == "inflow", Transaction.amount),
                else_=Decimal("0.00"),
            )
        ),
        Decimal("0.00"),
    )
    outflow_sum = func.coalesce(
        func.sum(
            case(
                (Transaction.direction == "outflow", Transaction.amount),
                else_=Decimal("0.00"),
            )
        ),
        Decimal("0.00"),
    )

    stmt = (
        select(
            Transaction.operation_date,
            inflow_sum.label("inflow"),
            outflow_sum.label("outflow"),
        )
        .where(*base_conditions)
        .group_by(Transaction.operation_date)
        .order_by(Transaction.operation_date.asc())
    )
    result = await session.execute(stmt)
    rows = result.all()

    daily_map: dict[date, tuple[Decimal, Decimal]] = {
        row[0]: (row[1], row[2]) for row in rows
    }

    # Generate dense daily series from date_from to date_to
    items: list[DailyAnalyticsItem] = []
    total_inflow = Decimal("0.00")
    total_outflow = Decimal("0.00")

    curr = date_from
    while curr <= date_to:
        inflow, outflow = daily_map.get(curr, (Decimal("0.00"), Decimal("0.00")))
        net = inflow - outflow
        total_inflow += inflow
        total_outflow += outflow

        items.append(
            DailyAnalyticsItem(
                date=curr.isoformat(),
                inflow=format_decimal(inflow),
                outflow=format_decimal(outflow),
                net_cash_flow=format_decimal(net),
            )
        )
        curr += timedelta(days=1)

    totals = DailyAnalyticsTotals(
        inflow=format_decimal(total_inflow),
        outflow=format_decimal(total_outflow),
        net_cash_flow=format_decimal(total_inflow - total_outflow),
    )

    return DailyAnalyticsResponse(items=items, totals=totals)


async def get_category_analytics(
    session: AsyncSession,
    company_id: int,
    date_from: date,
    date_to: date,
    direction: str | None = None,
    category_id: int | None = None,
    uncategorized: bool = False,
) -> CategoryAnalyticsResponse:
    base_conditions = [
        Transaction.company_id == company_id,
        Transaction.operation_date >= date_from,
        Transaction.operation_date <= date_to,
    ]
    if direction is not None:
        base_conditions.append(Transaction.direction == direction)
    if uncategorized:
        base_conditions.append(Transaction.category_id.is_(None))
    elif category_id is not None:
        base_conditions.append(Transaction.category_id == category_id)

    inflow_sum = func.coalesce(
        func.sum(
            case(
                (Transaction.direction == "inflow", Transaction.amount),
                else_=Decimal("0.00"),
            )
        ),
        Decimal("0.00"),
    )
    outflow_sum = func.coalesce(
        func.sum(
            case(
                (Transaction.direction == "outflow", Transaction.amount),
                else_=Decimal("0.00"),
            )
        ),
        Decimal("0.00"),
    )

    stmt = (
        select(
            Transaction.category_id,
            Category.name,
            inflow_sum.label("inflow"),
            outflow_sum.label("outflow"),
        )
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(*base_conditions)
        .group_by(Transaction.category_id, Category.name)
        .order_by(Category.name.nulls_last())
    )
    result = await session.execute(stmt)
    rows = result.all()

    items: list[CategoryAnalyticsItem] = []
    for cat_id, cat_name, inflow, outflow in rows:
        name = cat_name if cat_name is not None else "Без категории"
        net = inflow - outflow
        items.append(
            CategoryAnalyticsItem(
                category_id=cat_id,
                category_name=name,
                inflow=format_decimal(inflow),
                outflow=format_decimal(outflow),
                net_cash_flow=format_decimal(net),
            )
        )

    return CategoryAnalyticsResponse(items=items)
