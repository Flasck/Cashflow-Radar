import hmac
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    check_origin,
    get_current_user,
    get_current_user_and_token,
    require_csrf,
)
from app.auth_sessions import issue_tokens, token_hash
from app.crud.users import create_user
from app.db.connection import get_db
from app.email_verification import MAX_ATTEMPTS, hash_code, issue_code, retry_after
from app.errors import AppError, ConflictError, ForbiddenError, UnauthorizedError
from app.models.auth_session import AuthSession
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegistrationResponse,
    TokenResponse,
    UserResponse,
    VerificationRequest,
)
from app.security import (
    decode_token,
    hash_password,
    verify_csrf,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
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
    check_origin(request, required=False)
    existing = await _locked_user(session, payload.email)
    if existing is not None:
        if existing.email_verified:
            raise ConflictError(
                message="Пользователь с таким email уже существует", code="EMAIL_EXISTS"
            )
        if verify_password(payload.password, existing.password_hash):
            return RegistrationResponse(
                email=existing.email, retry_after=retry_after(existing)
            )
        await issue_code(existing)
        existing.full_name = payload.full_name.strip()
        existing.password_hash = hash_password(payload.password)
        await session.commit()
        return RegistrationResponse(
            email=existing.email, retry_after=retry_after(existing)
        )

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
    return RegistrationResponse(email=user.email, retry_after=retry_after(user))


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
    check_origin(request, required=False)
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
    return RegistrationResponse(email=user.email, retry_after=retry_after(user))


@router.post("/verification/status", response_model=RegistrationResponse)
async def verification_status(
    request: Request,
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RegistrationResponse:
    check_origin(request, required=False)
    user = await _locked_user(session, payload.email)
    _check_password(user, payload.password)
    assert user is not None
    return RegistrationResponse(
        email=user.email,
        status="verified" if user.email_verified else "verification_required",
        retry_after=retry_after(user),
    )


@router.post("/verify-email", response_model=TokenResponse)
async def verify_email(
    request: Request,
    payload: VerificationRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    check_origin(request, required=False)
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
    return await issue_tokens(session, response, user)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    check_origin(request, required=False)
    user = await _locked_user(session, payload.email)
    _check_password(user, payload.password)
    assert user is not None
    if not user.email_verified:
        raise AppError(
            403,
            "EMAIL_NOT_VERIFIED",
            "Подтвердите почту кодом из письма",
            fields={"email": user.email, "retry_after": str(retry_after(user))},
        )

    return await issue_tokens(session, response, user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    payload: RefreshRequest | None = None,
) -> TokenResponse:
    token = payload.refresh_token if payload else request.cookies.get("refresh_token")
    if not token:
        raise UnauthorizedError(message="Требуется refresh-токен")
    claims = decode_token(token, "refresh")
    if payload is not None:
        check_origin(request, required=False)
    if payload is None:
        check_origin(request)
        if not verify_csrf(request.headers.get("X-CSRF-Token"), claims.get("csrf")):
            raise ForbiddenError(message="Неверный CSRF-токен", code="INVALID_CSRF")
    try:
        user_id = int(claims["sub"])
    except (ValueError, TypeError):
        raise UnauthorizedError(code="INVALID_TOKEN") from None
    user = await session.scalar(
        select(User).where(User.id == user_id).with_for_update()
    )
    if (
        user is None
        or claims.get("version") != user.session_version
        or not user.email_verified
    ):
        raise UnauthorizedError(code="SESSION_REVOKED")
    auth_session = await session.scalar(
        select(AuthSession).where(AuthSession.id == claims.get("sid")).with_for_update()
    )
    if (
        auth_session is None
        or auth_session.user_id != user.id
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= datetime.now(UTC)
    ):
        raise UnauthorizedError(code="SESSION_REVOKED")
    if not hmac.compare_digest(auth_session.refresh_hash, token_hash(token)):
        auth_session.revoked_at = datetime.now(UTC)
        await session.commit()
        raise UnauthorizedError(
            message="Refresh-токен уже использован. Войдите заново.",
            code="REFRESH_REUSED",
        )
    return await issue_tokens(session, response, user, auth_session)


@router.post("/logout")
async def logout(
    response: Response,
    auth: Annotated[tuple[User, dict], Depends(get_current_user_and_token)],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, str]:
    current, claims = auth
    user = await session.scalar(
        select(User).where(User.id == current.id).with_for_update()
    )
    assert user is not None
    if "sid" in claims:
        auth_session = await session.get(
            AuthSession, claims["sid"], with_for_update=True
        )
        if auth_session is not None:
            auth_session.revoked_at = datetime.now(UTC)
    else:
        user.session_version += 1
    await session.commit()
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
