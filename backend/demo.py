import asyncio
import io
import sys
from datetime import date
from decimal import Decimal

if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8")

from app.crud.categories import get_category_by_name, list_categories
from app.crud.transactions import (
    add_split,
    check_splits_total,
    create_transaction,
    delete_transaction,
    get_transaction,
    get_transaction_with_splits,
    list_transactions,
    list_transactions_with_splits,
    update_transaction_purpose,
)
from app.crud.users import list_users
from app.db.connection import SessionFactory, engine
from app.models.split import TransactionSplit
from sqlalchemy import select


async def main() -> None:

    print("--- Исходные данные в базе ---")
    async with SessionFactory() as session:
        users = await list_users(session)
        print("Пользователи:", [(u.full_name, u.role) for u in users])

        categories = await list_categories(session)
        print("Категории:", [c.name for c in categories])

        transactions = await list_transactions_with_splits(session)
        print(f"Всего операций в базе: {len(transactions)}")

    print("\n--- Создание операции ---")
    async with SessionFactory() as session:
        cat_rev = await get_category_by_name(session, "Выручка")
        cat_mat = await get_category_by_name(session, "Материалы")
        assert cat_rev and cat_mat

        tx = await create_transaction(
            session,
            operation_date=date(2026, 10, 8),
            amount=Decimal("45000.00"),
            direction="inflow",
            purpose="Тестовый платеж",
        )
        tx_id = tx.id

        await add_split(session, tx_id, cat_rev.id, Decimal("30000.00"))
        await add_split(session, tx_id, cat_mat.id, Decimal("15000.00"))
        await check_splits_total(session, tx_id)

        await session.commit()
        print(f"Создана операция id={tx_id} на 45000р (30000 + 15000)")

    print("\n--- Проверка сплитом (m:n) ---")
    async with SessionFactory() as session:
        tx = await get_transaction_with_splits(session, tx_id)
        assert tx
        splits_info = [(s.category.name, s.allocated_amount) for s in tx.splits]
        print(f"Операция id={tx.id}: '{tx.purpose}', сплиты: {splits_info}")

        stmt = select(TransactionSplit).where(
            TransactionSplit.category_id == cat_rev.id
        )
        res = await session.execute(stmt)
        splits = res.scalars().all()
        print(f"Категория 'Выручка' используется в {len(splits)} операциях (связь M:N)")

    print("\n--- Обновление  ---")
    async with SessionFactory() as session:
        await update_transaction_purpose(
            session, tx_id, "Уточненное назначение платежа"
        )
        await session.commit()

    async with SessionFactory() as session:
        updated = await get_transaction(session, tx_id)
        assert updated
        print(f"Новое назначение из базы: '{updated.purpose}'")

    print("\n--- Удаление (DELETE) ---")
    async with SessionFactory() as session:
        await delete_transaction(session, tx_id)
        await session.commit()

    async with SessionFactory() as session:
        check = await get_transaction(session, tx_id)
        stmt = select(TransactionSplit).where(TransactionSplit.transaction_id == tx_id)
        res = await session.execute(stmt)
        orphan_splits = res.scalars().all()

        print(f"Операция удалена: {check is None}")
        print(f"Сплиты каскадно удалены: {len(orphan_splits) == 0}")

        all_tx = await list_transactions(session)
        print(f"Осталось исходных операций: {len(all_tx)}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
