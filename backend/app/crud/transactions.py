from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.split import TransactionSplit
from app.models.transaction import Transaction


async def create_transaction(
    session: AsyncSession,
    operation_date: date,
    amount: Decimal,
    direction: str,
    purpose: str | None = None,
) -> Transaction:
    transaction = Transaction(
        operation_date=operation_date,
        amount=amount,
        direction=direction,
        purpose=purpose,
    )
    session.add(transaction)
    await session.flush()
    return transaction


async def get_transaction(
    session: AsyncSession, transaction_id: int
) -> Transaction | None:
    return await session.get(Transaction, transaction_id)


async def get_transaction_with_splits(
    session: AsyncSession, transaction_id: int
) -> Transaction | None:
    stmt = (
        select(Transaction)
        .options(
            selectinload(Transaction.splits).selectinload(TransactionSplit.category)
        )
        .where(Transaction.id == transaction_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_transactions(session: AsyncSession) -> Sequence[Transaction]:
    stmt = select(Transaction).order_by(Transaction.operation_date, Transaction.id)
    result = await session.execute(stmt)
    return result.scalars().all()


async def list_transactions_with_splits(
    session: AsyncSession,
) -> Sequence[Transaction]:
    stmt = (
        select(Transaction)
        .options(
            selectinload(Transaction.splits).selectinload(TransactionSplit.category)
        )
        .order_by(Transaction.operation_date, Transaction.id)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def update_transaction_purpose(
    session: AsyncSession, transaction_id: int, purpose: str | None
) -> Transaction | None:
    transaction = await get_transaction(session, transaction_id)
    if transaction is None:
        return None
    transaction.purpose = purpose
    await session.flush()
    return transaction


async def delete_transaction(session: AsyncSession, transaction_id: int) -> bool:
    transaction = await get_transaction(session, transaction_id)
    if transaction is None:
        return False
    await session.delete(transaction)
    await session.flush()
    return True


async def add_split(
    session: AsyncSession,
    transaction_id: int,
    category_id: int,
    allocated_amount: Decimal,
) -> TransactionSplit:
    split = TransactionSplit(
        transaction_id=transaction_id,
        category_id=category_id,
        allocated_amount=allocated_amount,
    )
    session.add(split)
    await session.flush()
    return split


async def check_splits_total(session: AsyncSession, transaction_id: int) -> bool:
    transaction = await get_transaction(session, transaction_id)
    if transaction is None:
        raise ValueError(f"Операция id={transaction_id} не найдена")

    stmt = select(TransactionSplit).where(
        TransactionSplit.transaction_id == transaction_id
    )
    result = await session.execute(stmt)
    splits = result.scalars().all()

    total = sum((s.allocated_amount for s in splits), Decimal("0.00"))
    if total != transaction.amount:
        raise ValueError(
            f"Сумма частей ({total}) не равна сумме операции ({transaction.amount})"
        )
    return True
