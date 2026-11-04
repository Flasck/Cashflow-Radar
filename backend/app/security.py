import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.config import get_settings
from app.errors import UnauthorizedError

_password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _password_hasher.verify(plain_password, hashed_password)


def generate_csrf_token() -> str:
    return secrets.token_hex(32)


def create_access_token(user_id: int, csrf_token: str) -> str:
    settings = get_settings()
    if not settings.jwt_secret:
        raise ValueError(
            "RADAR_JWT_SECRET environment variable is required and cannot be empty"
        )

    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "csrf": csrf_token,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.jwt_secret:
        raise ValueError(
            "RADAR_JWT_SECRET environment variable is required and cannot be empty"
        )

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError(
            message="Срок действия сессии истек", code="TOKEN_EXPIRED"
        )
    except jwt.InvalidTokenError:
        raise UnauthorizedError(
            message="Недействительный токен авторизации", code="INVALID_TOKEN"
        )


def verify_csrf(header_csrf_token: str | None, token_csrf_claim: str | None) -> bool:
    if not header_csrf_token or not token_csrf_claim:
        return False
    return hmac.compare_digest(header_csrf_token, token_csrf_claim)
