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


def create_access_token(
    user_id: int,
    csrf_token: str,
    session_version: int = 0,
    session_id: str | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "csrf": csrf_token,
        "version": session_version,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }
    if session_id is not None:
        payload["sid"] = session_id
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    return decode_token(token, "access")


def create_refresh_token(
    user_id: int,
    session_id: str,
    csrf_token: str,
    session_version: int,
    expires_at: datetime,
) -> str:
    settings = get_settings()
    return jwt.encode(
        {
            "sub": str(user_id),
            "sid": session_id,
            "jti": secrets.token_hex(32),
            "csrf": csrf_token,
            "version": session_version,
            "type": "refresh",
            "iat": int(datetime.now(UTC).timestamp()),
            "exp": int(expires_at.timestamp()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str, token_type: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
        if payload.get("type", "access") != token_type:
            raise jwt.InvalidTokenError("Wrong token type")
        if token_type == "refresh" and any(
            not isinstance(payload.get(key), str) or not payload[key]
            for key in ("sid", "jti", "csrf")
        ):
            raise jwt.InvalidTokenError("Missing refresh claims")
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
