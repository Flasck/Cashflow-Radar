from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUserDependency, get_current_user, get_session
from app.crud.transactions import (
    add_split as add_transaction_split,
    check_splits_total,
    create_transaction as create_transaction_record,
    delete_transaction as delete_transaction_record,
    get_transaction_with_splits,
    list_transactions_with_splits,
    update_transaction_purpose,
)
from app.schemas.transactions import (
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
)


router = APIRouter(
    prefix="/transactions",
    tags=["transactions"],
    dependencies=[Depends(get_current_user)],
)
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[TransactionResponse])
async def list_transactions(session: SessionDependency):
    return await list_transactions_with_splits(session)


@router.post(
    "",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_transaction(
    data: TransactionCreate,
    session: SessionDependency,
    current_user: CurrentUserDependency,
):
    try:
        transaction = await create_transaction_record(
            session,
            operation_date=data.operation_date,
            amount=data.amount,
            direction=data.direction,
            purpose=data.purpose,
        )
        for split in data.splits:
            await add_transaction_split(
                session,
                transaction_id=transaction.id,
                category_id=split.category_id,
                allocated_amount=split.allocated_amount,
            )
        await check_splits_total(session, transaction.id)
        await session.commit()
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transaction or split conflicts with existing data",
        ) from exc

    return await get_transaction_with_splits(session, transaction.id)


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: int,
    session: SessionDependency,
):
    transaction = await get_transaction_with_splits(session, transaction_id)
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    return transaction


@router.patch("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: int,
    data: TransactionUpdate,
    session: SessionDependency,
):
    transaction = await update_transaction_purpose(
        session,
        transaction_id=transaction_id,
        purpose=data.purpose,
    )
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )

    await session.commit()
    return await get_transaction_with_splits(session, transaction_id)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: int,
    session: SessionDependency,
) -> Response:
    deleted = await delete_transaction_record(session, transaction_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )

    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
