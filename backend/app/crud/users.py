from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def create_user(
    session: AsyncSession,
    full_name: str,
    email: str,
    role: str,
    password_hash: str | None = None,
) -> User:
    user = User(
        full_name=full_name,
        email=email.strip().lower(),
        role=role,
        password_hash=password_hash,
    )
    session.add(user)
    await session.flush()
    return user


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email.strip().lower())
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_users(session: AsyncSession) -> Sequence[User]:
    stmt = select(User).order_by(User.id)
    result = await session.execute(stmt)
    return result.scalars().all()


async def update_user(
    session: AsyncSession,
    user_id: int,
    full_name: str | None = None,
    role: str | None = None,
) -> User | None:
    user = await get_user(session, user_id)
    if user is None:
        return None
    if full_name is not None:
        user.full_name = full_name
    if role is not None:
        user.role = role
    await session.flush()
    return user


async def delete_user(session: AsyncSession, user_id: int) -> bool:
    user = await get_user(session, user_id)
    if user is None:
        return False
    await session.delete(user)
    await session.flush()
    return True
