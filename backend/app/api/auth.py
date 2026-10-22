from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUserDependency, get_session
from app.crud.users import create_user, get_user_by_email
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.security import create_access_token, get_password_hash, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(data: RegisterRequest, session: SessionDependency):
    if await get_user_by_email(session, str(data.email)) is not None:
        raise HTTPException(status_code=409, detail="Email is already registered")

    user = await create_user(
        session,
        full_name=data.full_name.strip(),
        email=str(data.email),
        role="treasurer",
        password_hash=get_password_hash(data.password),
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="Email is already registered"
        ) from exc

    await session.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, session: SessionDependency):
    user = await get_user_by_email(session, str(data.email))
    if user is None or user.password_hash is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return TokenResponse(
        access_token=create_access_token(user.id),
        token_type="bearer",
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUserDependency):
    return current_user
