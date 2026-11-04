import hmac
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import check_origin, get_current_user, require_csrf
from app.crud.users import create_user, get_user_by_email
from app.db.connection import get_db
from app.email_verification import MAX_ATTEMPTS, hash_code, issue_code
from app.errors import AppError, ConflictError, ForbiddenError, UnauthorizedError
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RegistrationResponse,
    UserResponse,
    VerificationRequest,
)
from app.security import (
    create_access_token,
    generate_csrf_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(response: Response, user_id: int) -> None:
    csrf_token = generate_csrf_token()
    token = create_access_token(user_id=user_id, csrf_token=csrf_token)

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        path="/",
        secure=False,
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        samesite="lax",
        path="/",
        secure=False,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="csrf_token", path="/")


@router.post(
    "/register",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: Request,
    payload: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RegistrationResponse:
    check_origin(request)
    existing = await _locked_user(session, payload.email)
    if existing is not None:
        if existing.email_verified:
            raise ConflictError(
                message="Пользователь с таким email уже существует", code="EMAIL_EXISTS"
            )
        await issue_code(existing)
        existing.full_name = payload.full_name.strip()
        existing.password_hash = hash_password(payload.password)
        await session.commit()
        return RegistrationResponse(email=existing.email)

    try:
        user = await create_user(
            session=session,
            full_name=payload.full_name,
            email=payload.email,
            password_hash=hash_password(payload.password),
        )
        await issue_code(user)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ConflictError(
            message="Регистрация уже начата. Попробуйте войти или повторить отправку.",
            code="EMAIL_EXISTS",
        ) from None
    return RegistrationResponse(email=user.email)


async def _locked_user(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(
        select(User).where(User.email == email.strip().lower()).with_for_update()
    )


def _check_password(user: User | None, password: str) -> None:
    if user is None or not verify_password(password, user.password_hash):
        raise UnauthorizedError(
            message="Неверный email или пароль", code="INVALID_CREDENTIALS"
        )


@router.post("/resend-code", response_model=RegistrationResponse)
async def resend_code(
    request: Request,
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RegistrationResponse:
    check_origin(request)
    user = await _locked_user(session, payload.email)
    _check_password(user, payload.password)
    assert user is not None
    if user.email_verified:
        raise ConflictError(
            message="Почта уже подтверждена. Войдите в аккаунт.",
            code="EMAIL_ALREADY_VERIFIED",
        )
    await issue_code(user)
    await session.commit()
    return RegistrationResponse(email=user.email)


@router.post("/verify-email", response_model=UserResponse)
async def verify_email(
    request: Request,
    payload: VerificationRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    check_origin(request)
    user = await _locked_user(session, payload.email)
    if user is None or user.email_verified or not user.verification_code_hash:
        raise AppError(
            400, "INVALID_VERIFICATION_CODE", "Неверный или уже использованный код"
        )
    if (
        user.verification_expires_at is None
        or user.verification_expires_at <= datetime.now(UTC)
    ):
        raise AppError(400, "VERIFICATION_CODE_EXPIRED", "Код истёк. Запросите новый.")
    if user.verification_attempts >= MAX_ATTEMPTS:
        raise AppError(
            429,
            "VERIFICATION_ATTEMPTS_EXCEEDED",
            "Слишком много попыток. Запросите новый код.",
        )
    if not hmac.compare_digest(
        user.verification_code_hash, hash_code(user.email, payload.code)
    ):
        user.verification_attempts += 1
        await session.commit()
        raise AppError(400, "INVALID_VERIFICATION_CODE", "Неверный код подтверждения")
    user.email_verified = True
    user.verification_code_hash = None
    user.verification_expires_at = None
    user.verification_sent_at = None
    user.verification_attempts = 0
    await session.commit()
    _set_auth_cookies(response, user.id)
    return UserResponse(id=user.id, full_name=user.full_name, email=user.email)


@router.post("/login", response_model=UserResponse)
async def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    check_origin(request)
    user = await get_user_by_email(session, payload.email)
    _check_password(user, payload.password)
    assert user is not None
    if not user.email_verified:
        raise ForbiddenError(
            message="Подтвердите почту кодом из письма", code="EMAIL_NOT_VERIFIED"
        )

    _set_auth_cookies(response, user.id)
    return UserResponse(id=user.id, full_name=user.full_name, email=user.email)


@router.post("/logout")
async def logout(
    response: Response,
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, str]:
    _clear_auth_cookies(response)
    return {"status": "ok"}


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
    )
