import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.auth_session import AuthSession
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.security import create_access_token, create_refresh_token, generate_csrf_token


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def issue_tokens(
    session: AsyncSession,
    response: Response,
    user: User,
    auth_session: AuthSession | None = None,
) -> TokenResponse:
    settings = get_settings()
    if auth_session is None:
        auth_session = AuthSession(
            id=secrets.token_hex(16),
            user_id=user.id,
            expires_at=datetime.now(UTC)
            + timedelta(days=settings.refresh_token_expire_days),
        )
        session.add(auth_session)
    csrf = generate_csrf_token()
    access = create_access_token(user.id, csrf, user.session_version, auth_session.id)
    refresh = create_refresh_token(
        user.id, auth_session.id, csrf, user.session_version, auth_session.expires_at
    )
    auth_session.refresh_hash = token_hash(refresh)
    await session.commit()
    access_seconds = settings.access_token_expire_minutes * 60
    refresh_seconds = max(
        0, int((auth_session.expires_at - datetime.now(UTC)).total_seconds())
    )
    for key, value, httponly, max_age in (
        ("access_token", access, True, access_seconds),
        ("refresh_token", refresh, True, refresh_seconds),
        ("csrf_token", csrf, False, refresh_seconds),
    ):
        response.set_cookie(
            key=key,
            value=value,
            httponly=httponly,
            samesite="lax",
            path="/",
            secure=False,
            max_age=max_age,
        )
    response.headers["Cache-Control"] = "no-store"
    return TokenResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        access_token=access,
        refresh_token=refresh,
        expires_in=access_seconds,
    )
