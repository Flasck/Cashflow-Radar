from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.membership import Membership
from app.models.user import User


async def get_membership(
    session: AsyncSession,
    company_id: int,
    user_id: int,
) -> Membership | None:
    stmt = select(Membership).where(
        Membership.company_id == company_id,
        Membership.user_id == user_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_members(
    session: AsyncSession,
    company_id: int,
) -> Sequence[tuple[Membership, User]]:
    stmt = (
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.company_id == company_id)
        .order_by(Membership.user_id)
    )
    result = await session.execute(stmt)
    return result.all()


async def update_member_role(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    role: str,
) -> Membership | None:
    membership = await get_membership(session, company_id, user_id)
    if membership is None:
        return None
    membership.role = role
    await session.flush()
    return membership


async def delete_membership(
    session: AsyncSession,
    company_id: int,
    user_id: int,
) -> bool:
    membership = await get_membership(session, company_id, user_id)
    if membership is None:
        return False
    await session.delete(membership)
    await session.flush()
    return True
