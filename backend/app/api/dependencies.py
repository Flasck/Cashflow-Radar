from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Cookie, Depends, Header, Path, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.crud.members import get_membership
from app.crud.users import get_user
from app.db.connection import get_db
from app.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.models.auth_session import AuthSession
from app.models.membership import Membership
from app.models.user import User
from app.security import decode_access_token, verify_csrf

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")


def check_origin(request: Request, *, required: bool = True) -> None:
    origin = request.headers.get("origin")
    if not origin:
        referer = request.headers.get("referer")
        if referer:
            parsed = urlsplit(referer)
            origin = f"{parsed.scheme}://{parsed.netloc}"
    if not origin:
        if not required and not request.headers.get("sec-fetch-site"):
            return
        raise ForbiddenError(
            message="Заголовок Origin обязателен для выполнения операции",
            code="MISSING_ORIGIN",
        )
    settings = get_settings()
    if origin not in [*settings.allowed_origins, "http://localhost:8000"]:
        raise ForbiddenError(
            message="Запрещенный источник запроса (Origin)", code="INVALID_ORIGIN"
        )


async def get_current_user_and_token(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    access_token: Annotated[str | None, Cookie()] = None,
) -> tuple[User, dict]:
    if request.headers.get("authorization"):
        if credentials is None:
            raise UnauthorizedError(
                message="Ожидается Bearer-токен", code="INVALID_TOKEN"
            )
        access_token = credentials.credentials
    if not access_token:
        raise UnauthorizedError(message="Требуется авторизация", code="UNAUTHORIZED")

    payload = decode_access_token(access_token)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedError(message="Недействительный токен", code="INVALID_TOKEN")

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise UnauthorizedError(
            message="Недействительный идентификатор пользователя", code="INVALID_TOKEN"
        )

    user = await get_user(session, user_id)
    if user is None:
        raise UnauthorizedError(message="Пользователь не найден", code="USER_NOT_FOUND")
    if payload.get("version", 0) != user.session_version:
        raise UnauthorizedError(
            message="Войдите заново после смены пароля", code="SESSION_REVOKED"
        )
    if not user.email_verified:
        raise ForbiddenError(
            message="Сначала подтвердите почту", code="EMAIL_NOT_VERIFIED"
        )

    if "sid" in payload:
        auth_session = await session.get(AuthSession, payload["sid"])
        if (
            auth_session is None
            or auth_session.user_id != user.id
            or auth_session.revoked_at is not None
            or auth_session.expires_at <= datetime.now(UTC)
        ):
            raise UnauthorizedError(message="Сессия завершена", code="SESSION_REVOKED")

    return user, payload


async def get_current_user(
    user_and_token: Annotated[tuple[User, dict], Depends(get_current_user_and_token)],
) -> User:
    return user_and_token[0]


def require_csrf(
    request: Request,
    user_and_token: Annotated[tuple[User, dict], Depends(get_current_user_and_token)],
    x_csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> None:
    if request.headers.get("authorization"):
        return
    check_origin(request)
    _, payload = user_and_token
    csrf_claim = payload.get("csrf")
    if not verify_csrf(x_csrf_token, csrf_claim):
        raise ForbiddenError(
            message="Неверный или отсутствующий CSRF-токен", code="INVALID_CSRF"
        )


def require_role(*roles: str):
    async def dependency(
        company_id: Annotated[
            int, Path(openapi_examples={"existing_company": {"value": 69}})
        ],
        user_and_token: Annotated[
            tuple[User, dict], Depends(get_current_user_and_token)
        ],
        session: Annotated[AsyncSession, Depends(get_db)],
    ) -> Membership:
        user, _ = user_and_token
        membership = await get_membership(session, company_id, user.id)
        if membership is None:
            raise NotFoundError(message="Компания не найдена", code="COMPANY_NOT_FOUND")

        if membership.role not in roles:
            raise ForbiddenError(
                message="Недостаточно прав для выполнения действия", code="FORBIDDEN"
            )

        return membership

    return dependency
