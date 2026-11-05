from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.config import get_settings
from app.db.connection import get_engine
from app.errors import (
    AppError,
    app_error_handler,
    unhandled_exception_handler,
    validation_error_handler,
)
from app.forecasting import close_forecast_channel

MAX_BODY_BYTES = 5 * 1024 * 1024


class RequestSizeLimitMiddleware:
    def __init__(self, app, max_bytes: int = MAX_BODY_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        too_large = JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "PAYLOAD_TOO_LARGE",
                    "message": "Размер запроса превышает допустимый лимит (5 МБ)",
                    "fields": {},
                }
            },
        )
        content_length = dict(scope.get("headers", [])).get(b"content-length", b"")
        if content_length.isdigit() and int(content_length) > self.max_bytes:
            await too_large(scope, receive, send)
            return

        body_chunks: list[bytes] = []
        total_received = 0

        while True:
            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                total_received += len(chunk)
                if total_received > self.max_bytes:
                    await too_large(scope, receive, send)
                    return

                body_chunks.append(chunk)
                if not message.get("more_body", False):
                    break
            elif message["type"] == "http.disconnect":
                return

        body = b"".join(body_chunks)
        has_sent = False

        async def replay_receive():
            nonlocal has_sent
            if not has_sent:
                has_sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield
    await close_forecast_channel()
    engine = get_engine()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Cashflow Radar API",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(RequestSizeLimitMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(api_router)

    return app


app = create_app()
