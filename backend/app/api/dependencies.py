from typing import Annotated

from fastapi import Cookie, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.crud.members import get_membership
from app.crud.users import get_user
from app.db.connection import get_db
from app.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.models.membership import Membership
from app.models.user import User
from app.security import decode_access_token, verify_csrf


def check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin:
        raise ForbiddenError(
            message="Заголовок Origin обязателен для выполнения операции",
            code="MISSING_ORIGIN",
        )
    settings = get_settings()
    if origin not in settings.allowed_origins:
        raise ForbiddenError(
            message="Запрещенный источник запроса (Origin)", code="INVALID_ORIGIN"
        )


async def get_current_user_and_token(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    access_token: Annotated[str | None, Cookie()] = None,
) -> tuple[User, dict]:
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
    if not user.email_verified:
        raise ForbiddenError(
            message="Сначала подтвердите почту", code="EMAIL_NOT_VERIFIED"
        )

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
    check_origin(request)
    _, payload = user_and_token
    csrf_claim = payload.get("csrf")
    if not verify_csrf(x_csrf_token, csrf_claim):
        raise ForbiddenError(
            message="Неверный или отсутствующий CSRF-токен", code="INVALID_CSRF"
        )


def require_role(*roles: str):
    async def dependency(
        company_id: int,
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
