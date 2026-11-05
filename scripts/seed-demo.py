import argparse
import asyncio
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.db.connection import get_engine, get_sessionmaker
from app.models.category import Category
from app.models.company import Company
from app.models.invitation import Invitation
from app.models.membership import Membership
from app.models.transaction import Transaction
from app.models.user import User
from app.security import hash_password
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

ACCOUNTS = {
    "anna": "Анна Миронова",
    "boris": "Борис Ковалёв",
    "vera": "Вера Лебедева",
    "igor": "Игорь Соколов",
    "olga": "Ольга Белова",
}


def email(alias: str) -> str:
    return f"demo.{alias}@example.com"


async def seed_demo(session: AsyncSession, password: str) -> bool:
    await session.execute(text("SELECT pg_advisory_xact_lock(7261646172)"))
    existing = set(
        await session.scalars(
            select(User.email).where(User.email.in_([email(a) for a in ACCOUNTS]))
        )
    )
    if len(existing) == len(ACCOUNTS):
        return False
    if existing:
        raise ValueError("Demo email collision; no existing accounts were changed.")

    users = {
        alias: User(
            full_name=name,
            email=email(alias),
            password_hash=hash_password(password),
            email_verified=True,
        )
        for alias, name in ACCOUNTS.items()
    }
    companies = {
        "north": Company(
            name="Демо · Северная мануфактура", industry_code="Производство"
        ),
        "studio": Company(name="Демо · Студия Линия", industry_code="Дизайн"),
        "bakery": Company(name="Демо · Пекарня Тёплый хлеб", industry_code="Пекарня"),
        "empty": Company(name="Демо · Новый проект", industry_code=None),
    }
    session.add_all([*users.values(), *companies.values()])
    await session.flush()
    for company, alias, role in [
        ("north", "anna", "owner"),
        ("north", "boris", "treasurer"),
        ("north", "vera", "viewer"),
        ("studio", "anna", "owner"),
        ("studio", "igor", "viewer"),
        ("bakery", "boris", "owner"),
        ("bakery", "vera", "treasurer"),
        ("empty", "anna", "owner"),
    ]:
        session.add(
            Membership(
                company_id=companies[company].id, user_id=users[alias].id, role=role
            )
        )

    today = datetime.now(ZoneInfo("Europe/Moscow")).date()
    for key, days, scale in [("north", 90, 3), ("bakery", 60, 1), ("studio", 6, 2)]:
        categories = [
            Category(company_id=companies[key].id, name=name)
            for name in ["Продажи", "Материалы", "Аренда", "Зарплата"]
        ]
        session.add_all(categories)
        await session.flush()
        for index in range(days):
            day = today - timedelta(days=days - index - 1)
            for direction, amount, category, purpose in [
                (
                    "inflow",
                    (14500 + index % 7 * 1200) * scale,
                    categories[0],
                    "Оплата заказов",
                ),
                (
                    "outflow",
                    (8200 + index % 5 * 850) * scale,
                    categories[1 + index % 3],
                    "Плановая выплата",
                ),
            ]:
                session.add(
                    Transaction(
                        company_id=companies[key].id,
                        operation_date=day,
                        amount=Decimal(amount),
                        direction=direction,
                        category_id=category.id,
                        purpose=f"Демо: {purpose}",
                    )
                )

    now = datetime.now(UTC)
    for key, alias, role, status, expired in [
        ("bakery", "anna", "viewer", "pending", False),
        ("north", "olga", "treasurer", "pending", False),
        ("bakery", "igor", "viewer", "pending", False),
        ("studio", "vera", "viewer", "declined", False),
        ("studio", "olga", "viewer", "revoked", False),
        ("bakery", "olga", "viewer", "pending", True),
        ("north", "boris", "treasurer", "accepted", False),
        ("north", "vera", "viewer", "accepted", False),
    ]:
        session.add(
            Invitation(
                company_id=companies[key].id,
                email=email(alias),
                role=role,
                token_hash=hashlib.sha256(secrets.token_bytes(32)).hexdigest(),
                created_at=now - timedelta(days=3 if expired else 1),
                expires_at=now + timedelta(days=-1 if expired else 2),
                status=status,
                responded_at=now - timedelta(hours=8) if status != "pending" else None,
            )
        )
    await session.flush()
    return True


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add fictional demo accounts and workspaces"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Confirm inserting demo data"
    )
    parser.add_argument("--database", required=True, help="Exact local database name")
    args = parser.parse_args()
    url = make_url(get_settings().database_url)
    if (
        not args.apply
        or url.host not in {"localhost", "127.0.0.1", "::1"}
        or url.database != args.database
    ):
        parser.error(
            "Requires --apply, a loopback database host and matching --database."
        )
    password = secrets.token_urlsafe(18)
    try:
        async with get_sessionmaker().begin() as session:
            created = await seed_demo(session, password)
        if created:
            print(
                "Created: 5 accounts, 4 companies, 8 memberships, 12 categories, 312 payments, 8 invitations."
            )
            print("Fictional local demo accounts only; no emails sent.")
            for alias in ACCOUNTS:
                print(email(alias))
            print(f"Demo-only password (all five accounts): {password}")
        else:
            print(
                "Demo accounts already exist; nothing changed, passwords were not reset."
            )
    finally:
        await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(main())
