from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category


async def create_category(session: AsyncSession, name: str) -> Category:
    category = Category(name=name.strip())
    session.add(category)
    await session.flush()
    return category


async def get_category(session: AsyncSession, catigory_id: int) -> Category | None:
    return await session.get(Category, catigory_id)


async def get_category_by_name(session: AsyncSession, name: str) -> Category | None:
    stmt = select(Category).where(Category.name == name.strip())
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_categories(session: AsyncSession) -> Sequence[Category]:
    stmt = select(Category).order_by(Category.id)
    result = await session.execute(stmt)
    return result.scalars().all()


async def update_category(
    session: AsyncSession, category_id: int, name: str
) -> Category | None:
    category = await get_category(session, category_id)
    if category is None:
        return None
    category.name = name.strip()
    await session.flush()
    return category


async def delete_category(session: AsyncSession, category_id: int) -> bool:
    category = await get_category(session, category_id)
    if category is None:
        return False
    await session.delete(category)
    await session.flush()
    return True
