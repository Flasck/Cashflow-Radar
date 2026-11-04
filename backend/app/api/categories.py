from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUserDependency, get_current_user, get_session
from app.crud.categories import (
    create_category as create_category_record,
)
from app.crud.categories import (
    delete_category as delete_category_record,
)
from app.crud.categories import (
    get_category as get_category_record,
)
from app.crud.categories import (
    list_categories as list_category_records,
)
from app.crud.categories import (
    update_category as update_category_record,
)
from app.schemas.categories import CategoryCreate, CategoryResponse, CategoryUpdate

router = APIRouter(
    prefix="/categories",
    tags=["categories"],
    dependencies=[Depends(get_current_user)],
)
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[CategoryResponse])
async def list_categories(session: SessionDependency):
    return await list_category_records(session)


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    data: CategoryCreate,
    session: SessionDependency,
    current_user: CurrentUserDependency,
):
    try:
        category = await create_category_record(session, name=data.name)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A category with this name already exists",
        ) from exc

    await session.refresh(category)
    return category


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(category_id: int, session: SessionDependency):
    category = await get_category_record(session, category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    return category


@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    data: CategoryUpdate,
    session: SessionDependency,
):
    category = await update_category_record(
        session,
        category_id=category_id,
        name=data.name,
    )
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A category with this name already exists",
        ) from exc

    await session.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    session: SessionDependency,
) -> Response:
    deleted = await delete_category_record(session, category_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category is used by one or more transactions",
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
