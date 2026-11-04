from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_csrf, require_role
from app.crud.categories import (
    create_category,
    delete_category,
    get_category,
    get_category_by_name,
    list_categories,
    update_category,
)
from app.db.connection import get_db
from app.errors import ConflictError, NotFoundError
from app.models.membership import Membership
from app.schemas.categories import CategoryCreate, CategoryResponse, CategoryUpdate

router = APIRouter(prefix="/companies/{company_id}/categories", tags=["categories"])


@router.get("", response_model=list[CategoryResponse])
async def get_categories(
    company_id: int,
    _membership: Annotated[
        Membership, Depends(require_role("owner", "treasurer", "viewer"))
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[CategoryResponse]:
    cats = await list_categories(session, company_id)
    return [
        CategoryResponse(id=c.id, company_id=c.company_id, name=c.name) for c in cats
    ]


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def add_category(
    company_id: int,
    payload: CategoryCreate,
    _membership: Annotated[Membership, Depends(require_role("owner", "treasurer"))],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> CategoryResponse:
    existing = await get_category_by_name(session, company_id, payload.name)
    if existing is not None:
        raise ConflictError(
            message="Категория с таким названием уже существует", code="CATEGORY_EXISTS"
        )

    cat = await create_category(session, company_id, payload.name)
    await session.commit()
    return CategoryResponse(id=cat.id, company_id=cat.company_id, name=cat.name)


@router.patch("/{category_id}", response_model=CategoryResponse)
async def edit_category(
    company_id: int,
    category_id: int,
    payload: CategoryUpdate,
    _membership: Annotated[Membership, Depends(require_role("owner", "treasurer"))],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> CategoryResponse:
    cat = await get_category(session, company_id, category_id)
    if cat is None:
        raise NotFoundError(message="Категория не найдена", code="CATEGORY_NOT_FOUND")

    existing = await get_category_by_name(session, company_id, payload.name)
    if existing is not None and existing.id != category_id:
        raise ConflictError(
            message="Категория с таким названием уже существует", code="CATEGORY_EXISTS"
        )

    updated = await update_category(session, company_id, category_id, payload.name)
    assert updated is not None
    await session.commit()
    return CategoryResponse(
        id=updated.id, company_id=updated.company_id, name=updated.name
    )


@router.delete("/{category_id}")
async def remove_category(
    company_id: int,
    category_id: int,
    _membership: Annotated[Membership, Depends(require_role("owner", "treasurer"))],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, str]:
    cat = await get_category(session, company_id, category_id)
    if cat is None:
        raise NotFoundError(message="Категория не найдена", code="CATEGORY_NOT_FOUND")

    try:
        deleted = await delete_category(session, company_id, category_id)
        if not deleted:
            raise NotFoundError(
                message="Категория не найдена", code="CATEGORY_NOT_FOUND"
            )
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ConflictError(
            message="Невозможно удалить категорию, к которой привязаны операции",
            code="CATEGORY_IN_USE",
        )

    return {"status": "ok"}
