from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category


async def create_category(
    session: AsyncSession,
    company_id: int,
    name: str,
) -> Category:
    category = Category(
        company_id=company_id,
        name=name.strip(),
    )
    session.add(category)
    await session.flush()
    return category


async def get_category(
    session: AsyncSession,
    company_id: int,
    category_id: int,
) -> Category | None:
    stmt = select(Category).where(
        Category.company_id == company_id,
        Category.id == category_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_category_by_name(
    session: AsyncSession,
    company_id: int,
    name: str,
) -> Category | None:
    stmt = select(Category).where(
        Category.company_id == company_id,
        func.lower(Category.name) == name.strip().lower(),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_categories(
    session: AsyncSession,
    company_id: int,
) -> Sequence[Category]:
    stmt = (
        select(Category)
        .where(Category.company_id == company_id)
        .order_by(Category.name)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def update_category(
    session: AsyncSession,
    company_id: int,
    category_id: int,
    name: str,
) -> Category | None:
    category = await get_category(session, company_id, category_id)
    if category is None:
        return None
    category.name = name.strip()
    await session.flush()
    return category


async def delete_category(
    session: AsyncSession,
    company_id: int,
    category_id: int,
) -> bool:
    category = await get_category(session, company_id, category_id)
    if category is None:
        return False
    await session.delete(category)
    await session.flush()
    return True
