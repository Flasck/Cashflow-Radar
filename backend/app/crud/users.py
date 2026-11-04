from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def create_user(
    session: AsyncSession,
    full_name: str,
    email: str,
    password_hash: str,
    email_verified: bool = False,
) -> User:
    user = User(
        full_name=full_name.strip(),
        email=email.strip().lower(),
        password_hash=password_hash,
        email_verified=email_verified,
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
