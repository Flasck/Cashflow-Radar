from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.transaction import Transaction


async def create_transaction(
    session: AsyncSession,
    company_id: int,
    operation_date: date,
    amount: Decimal,
    direction: str,
    category_id: int | None = None,
    purpose: str | None = None,
) -> Transaction:
    tx = Transaction(
        company_id=company_id,
        operation_date=operation_date,
        amount=amount,
        direction=direction,
        category_id=category_id,
        purpose=purpose,
    )
    session.add(tx)
    await session.flush()
    return tx


async def get_transaction(
    session: AsyncSession,
    company_id: int,
    transaction_id: int,
) -> Transaction | None:
    stmt = select(Transaction).where(
        Transaction.company_id == company_id,
        Transaction.id == transaction_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_transaction_with_category(
    session: AsyncSession,
    company_id: int,
    transaction_id: int,
) -> tuple[Transaction, str | None] | None:
    stmt = (
        select(Transaction, Category.name)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(
            Transaction.company_id == company_id,
            Transaction.id == transaction_id,
        )
    )
    result = await session.execute(stmt)
    row = result.first()
    if row is None:
        return None
    return row[0], row[1]


async def list_transactions(
    session: AsyncSession,
    company_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
    direction: str | None = None,
    category_id: int | None = None,
    uncategorized: bool = False,
    page: int = 1,
    page_size: int = 50,
) -> tuple[Sequence[tuple[Transaction, str | None]], int]:
    base_conditions = [Transaction.company_id == company_id]

    if date_from is not None:
        base_conditions.append(Transaction.operation_date >= date_from)
    if date_to is not None:
        base_conditions.append(Transaction.operation_date <= date_to)
    if direction is not None:
        base_conditions.append(Transaction.direction == direction)
    if uncategorized:
        base_conditions.append(Transaction.category_id.is_(None))
    elif category_id is not None:
        base_conditions.append(Transaction.category_id == category_id)

    count_stmt = select(func.count(Transaction.id)).where(*base_conditions)
    total_result = await session.execute(count_stmt)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    items_stmt = (
        select(Transaction, Category.name)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(*base_conditions)
        .order_by(Transaction.operation_date.desc(), Transaction.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    items_result = await session.execute(items_stmt)
    items = items_result.all()

    return items, total


async def delete_transaction(
    session: AsyncSession,
    company_id: int,
    transaction_id: int,
) -> bool:
    tx = await get_transaction(session, company_id, transaction_id)
    if tx is None:
        return False
    await session.delete(tx)
    await session.flush()
    return True
