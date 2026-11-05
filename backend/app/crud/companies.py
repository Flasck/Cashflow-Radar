from collections.abc import Sequence
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError, UnauthorizedError
from app.models.company import Company
from app.models.membership import Membership
from app.models.transaction import Transaction
from app.models.user import User


async def create_company_with_owner(
    session: AsyncSession,
    name: str,
    industry_code: str | None,
    owner_user_id: int,
) -> tuple[Company, Membership]:
    user = await session.scalar(
        select(User).where(User.id == owner_user_id).with_for_update()
    )
    if user is None:
        raise UnauthorizedError(code="USER_NOT_FOUND")
    company = Company(
        name=name.strip(),
        industry_code=industry_code.strip() if industry_code else None,
    )
    session.add(company)
    await session.flush()

    membership = Membership(
        user_id=owner_user_id,
        company_id=company.id,
        role="owner",
    )
    session.add(membership)
    await session.flush()

    return company, membership


async def get_company(session: AsyncSession, company_id: int) -> Company | None:
    return await session.get(Company, company_id)


async def lock_company(session: AsyncSession, company_id: int) -> Company:
    company = await session.scalar(
        select(Company).where(Company.id == company_id).with_for_update()
    )
    if company is None:
        raise NotFoundError(message="Компания не найдена", code="COMPANY_NOT_FOUND")
    return company


async def list_user_companies(
    session: AsyncSession,
    user_id: int,
) -> Sequence[tuple[Company, str]]:
    stmt = (
        select(Company, Membership.role)
        .join(Membership, Membership.company_id == Company.id)
        .where(Membership.user_id == user_id)
        .order_by(Company.id)
    )
    result = await session.execute(stmt)
    return result.all()


async def get_company_last_operation_date(
    session: AsyncSession,
    company_id: int,
    max_date: date | None = None,
) -> date | None:
    stmt = select(func.max(Transaction.operation_date)).where(
        Transaction.company_id == company_id
    )
    if max_date is not None:
        stmt = stmt.where(Transaction.operation_date <= max_date)
    result = await session.execute(stmt)
    return result.scalar()
