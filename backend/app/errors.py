import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        fields: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.fields = fields or {}


class UnauthorizedError(AppError):
    def __init__(
        self, message: str = "Требуется аутентификация", code: str = "UNAUTHORIZED"
    ):
        super().__init__(401, code, message)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Недостаточно прав", code: str = "FORBIDDEN"):
        super().__init__(403, code, message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Объект не найден", code: str = "NOT_FOUND"):
        super().__init__(404, code, message)


class ConflictError(AppError):
    def __init__(
        self,
        message: str = "Конфликт данных",
        code: str = "CONFLICT",
        fields: dict[str, Any] | None = None,
    ):
        super().__init__(409, code, message, fields)


class PayloadTooLargeError(AppError):
    def __init__(
        self,
        message: str = "Превышен допустимый размер запроса",
        code: str = "PAYLOAD_TOO_LARGE",
    ):
        super().__init__(413, code, message)


class UnsupportedMediaTypeError(AppError):
    def __init__(
        self,
        message: str = "Неподдерживаемый формат данных",
        code: str = "UNSUPPORTED_MEDIA_TYPE",
    ):
        super().__init__(415, code, message)


class UnprocessableError(AppError):
    def __init__(
        self,
        message: str = "Некорректные параметры запроса",
        code: str = "UNPROCESSABLE_ENTITY",
        fields: dict[str, Any] | None = None,
    ):
        super().__init__(422, code, message, fields)


class BadGatewayError(AppError):
    def __init__(
        self,
        message: str = "Некорректный ответ сервиса прогнозирования",
        code: str = "BAD_GATEWAY",
    ):
        super().__init__(502, code, message)


class ServiceUnavailableError(AppError):
    def __init__(
        self,
        message: str = "Сервис прогнозирования временно недоступен",
        code: str = "SERVICE_UNAVAILABLE",
    ):
        super().__init__(503, code, message)


class GatewayTimeoutError(AppError):
    def __init__(
        self,
        message: str = "Превышено время ожидания ответа от сервиса прогнозирования",
        code: str = "GATEWAY_TIMEOUT",
    ):
        super().__init__(504, code, message)


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "fields": exc.fields,
            }
        },
    )


async def validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    fields: dict[str, str] = {}
    for err in exc.errors():
        loc = err.get("loc", ())
        path_parts = [str(part) for part in loc if part != "body"]
        field_path = ".".join(path_parts) if path_parts else "request"
        fields[field_path] = str(err.get("msg", "Некорректное значение"))

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Ошибка валидации переданных данных",
                "fields": fields,
            }
        },
    )


async def unhandled_exception_handler(
    _request: Request, exc: Exception
) -> JSONResponse:
    logger.error(
        "Внутренняя непредвиденная ошибка при обработке запроса: %s", type(exc).__name__
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Внутренняя ошибка сервера",
                "fields": {},
            }
        },
    )
