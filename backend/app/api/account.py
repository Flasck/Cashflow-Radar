import asyncio
import hashlib
import hmac
import math
import secrets
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import email_verification as mail
from app.api.dependencies import (
    get_current_user,
    get_current_user_and_token,
    require_csrf,
)
from app.auth_sessions import issue_tokens
from app.config import get_settings
from app.db.connection import get_db
from app.errors import AppError, ConflictError, ForbiddenError, UnauthorizedError
from app.models.invitation import Invitation
from app.models.membership import Membership
from app.models.user import User
from app.schemas.auth import (
    AccountDeleteRequest,
    PasswordChangeConfirm,
    PasswordChangeRequest,
    ProfileUpdate,
    RegistrationResponse,
    TokenResponse,
    UserResponse,
)
from app.security import hash_password, verify_password

router = APIRouter(prefix="/account", tags=["account"])


def password_code_hash(user: User, code: str) -> str:
    return hmac.new(
        get_settings().jwt_secret.encode(),
        f"password-change:{user.id}:{user.email}:{code}".encode(),
        hashlib.sha256,
    ).hexdigest()


async def locked_account(session: AsyncSession, auth: tuple[User, dict]) -> User:
    current, token = auth
    user = await session.scalar(
        select(User)
        .where(User.id == current.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    assert user is not None
    if token.get("version", 0) != user.session_version:
        raise UnauthorizedError(
            message="Сессия завершена. Войдите заново.", code="SESSION_REVOKED"
        )
    return user


@router.patch("", response_model=UserResponse)
async def update_profile(
    payload: ProfileUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> UserResponse:
    user.full_name = payload.full_name
    await session.commit()
    return UserResponse(id=user.id, full_name=user.full_name, email=user.email)


@router.delete("")
async def delete_account(
    payload: AccountDeleteRequest,
    response: Response,
    auth: Annotated[tuple[User, dict], Depends(get_current_user_and_token)],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, str]:
    user = await locked_account(session, auth)
    if not verify_password(payload.current_password, user.password_hash):
        raise ForbiddenError(
            message="Неверный текущий пароль", code="INVALID_CURRENT_PASSWORD"
        )
    owned_company = await session.scalar(
        select(Membership.company_id)
        .where(Membership.user_id == user.id, Membership.role == "owner")
        .limit(1)
    )
    if owned_company is not None:
        raise ConflictError(
            message="Сначала удалите компании, владельцем которых вы являетесь",
            code="ACCOUNT_OWNS_COMPANIES",
        )
    await session.execute(
        update(Invitation)
        .where(Invitation.email == user.email, Invitation.status == "pending")
        .values(status="revoked", responded_at=datetime.now(UTC))
    )
    await session.execute(delete(User).where(User.id == user.id))
    await session.commit()
    for key in ("access_token", "refresh_token", "csrf_token"):
        response.delete_cookie(key=key, path="/")
    return {"status": "ok"}


@router.post("/password/code", response_model=RegistrationResponse)
async def request_password_code(
    payload: PasswordChangeRequest,
    auth: Annotated[tuple[User, dict], Depends(get_current_user_and_token)],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> RegistrationResponse:
    user = await locked_account(session, auth)
    if not verify_password(payload.current_password, user.password_hash):
        raise ForbiddenError(
            message="Неверный текущий пароль", code="INVALID_CURRENT_PASSWORD"
        )
    if payload.current_password == payload.new_password:
        raise AppError(
            400, "PASSWORD_UNCHANGED", "Новый пароль должен отличаться от текущего"
        )
    now = datetime.now(UTC)
    if user.password_code_sent_at:
        remaining = math.ceil(
            (user.password_code_sent_at + mail.RESEND_INTERVAL - now).total_seconds()
        )
        if remaining > 0:
            raise AppError(
                429,
                "EMAIL_RATE_LIMIT",
                "Повторная отправка пока недоступна",
                fields={"retry_after": str(remaining)},
            )
    code = f"{secrets.randbelow(1_000_000):06d}"
    pending_hash = hash_password(payload.new_password)
    await asyncio.to_thread(
        mail.send_verification_email, user.email, code, password_change=True
    )
    user.password_change_hash = pending_hash
    user.password_code_hash = password_code_hash(user, code)
    user.password_code_sent_at = datetime.now(UTC)
    user.password_code_expires_at = user.password_code_sent_at + mail.CODE_LIFETIME
    user.password_code_attempts = 0
    await session.commit()
    return RegistrationResponse(
        email=user.email, status="password_change_required", retry_after=60
    )


@router.post("/password/confirm", response_model=TokenResponse)
async def confirm_password_change(
    payload: PasswordChangeConfirm,
    response: Response,
    auth: Annotated[tuple[User, dict], Depends(get_current_user_and_token)],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> TokenResponse:
    user = await locked_account(session, auth)
    if not user.password_code_hash or not user.password_change_hash:
        raise AppError(
            400, "INVALID_VERIFICATION_CODE", "Сначала запросите код смены пароля"
        )
    if (
        user.password_code_expires_at is None
        or user.password_code_expires_at <= datetime.now(UTC)
    ):
        raise AppError(400, "VERIFICATION_CODE_EXPIRED", "Код истёк. Запросите новый.")
    if user.password_code_attempts >= mail.MAX_ATTEMPTS:
        raise AppError(
            429,
            "VERIFICATION_ATTEMPTS_EXCEEDED",
            "Слишком много попыток. Запросите новый код.",
        )
    if not hmac.compare_digest(
        user.password_code_hash, password_code_hash(user, payload.code)
    ):
        user.password_code_attempts += 1
        await session.commit()
        raise AppError(400, "INVALID_VERIFICATION_CODE", "Неверный код подтверждения")
    user.password_hash = user.password_change_hash
    user.password_change_hash = None
    user.password_code_hash = None
    user.password_code_expires_at = None
    user.password_code_attempts = 0
    user.session_version += 1
    return await issue_tokens(session, response, user)
