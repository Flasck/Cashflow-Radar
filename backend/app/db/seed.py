import asyncio
import io
import sys
from datetime import date
from decimal import Decimal

if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8")

from app.crud.categories import create_category
from app.crud.transactions import (
    add_split,
    check_splits_total,
    create_transaction,
)
from app.crud.users import create_user, get_user_by_email
from app.db.connection import SessionFactory, engine
from app.security import get_password_hash


async def seed() -> None:
    async with SessionFactory() as session:
        if await get_user_by_email(session, "treasurer@example.com"):
            print("База уже заполнена, повторный запуск пропущен.")
            return

        await create_user(
            session,
            "вася",
            "treasurer@example.com",
            "treasurer",
            password_hash=get_password_hash("treasurer123"),
        )
        await create_user(
            session,
            "петя",
            "cfo@example.com",
            "cfo",
            password_hash=get_password_hash("cfo123456"),
        )

        cat_rev = await create_category(session, "Выручка")
        cat_rent = await create_category(session, "Аренда")
        cat_pay = await create_category(session, "Зарплата")
        cat_mat = await create_category(session, "Материалы")

        t1 = await create_transaction(
            session,
            operation_date=date(2026, 10, 1),
            amount=Decimal("150000.00"),
            direction="inflow",
            purpose="Оплата от покупателя",
        )
        await add_split(session, t1.id, cat_rev.id, Decimal("150000.00"))
        await check_splits_total(session, t1.id)

        t2 = await create_transaction(
            session,
            operation_date=date(2026, 10, 3),
            amount=Decimal("90000.00"),
            direction="outflow",
            purpose="Оплата сырья и аренды склада",
        )
        await add_split(session, t2.id, cat_mat.id, Decimal("60000.00"))
        await add_split(session, t2.id, cat_rent.id, Decimal("30000.00"))
        await check_splits_total(session, t2.id)

        t3 = await create_transaction(
            session,
            operation_date=date(2026, 10, 5),
            amount=Decimal("50000.00"),
            direction="outflow",
            purpose="Выплата аванса сотрудникам",
        )
        await add_split(session, t3.id, cat_pay.id, Decimal("50000.00"))
        await check_splits_total(session, t3.id)

        await session.commit()
        print("seed выполнился успешно")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
