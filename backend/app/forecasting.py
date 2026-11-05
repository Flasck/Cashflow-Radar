import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import grpc.aio
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import (
    BadGatewayError,
    GatewayTimeoutError,
    ServiceUnavailableError,
    UnprocessableError,
)
from app.models.transaction import Transaction
from app.schemas.common import format_decimal
from app.schemas.forecast import ForecastPoint, ForecastResponse
from contracts import forecast_pb2, forecast_pb2_grpc

MAX_HISTORY_DAYS = 1825
MIN_HISTORY_DAYS = 30
logger = logging.getLogger("uvicorn.error")

_channel: grpc.aio.Channel | None = None


def get_forecast_channel() -> grpc.aio.Channel:
    global _channel
    if _channel is None:
        settings = get_settings()
        _channel = grpc.aio.insecure_channel(settings.forecast_grpc_target)
    return _channel


async def close_forecast_channel() -> None:
    global _channel
    if _channel is not None:
        await _channel.close()
        _channel = None


async def get_dense_history_series(
    session: AsyncSession,
    company_id: int,
    history_end: date,
) -> tuple[list[tuple[date, Decimal]], date | None, list[str]]:
    bounds_stmt = select(
        func.min(Transaction.operation_date), func.max(Transaction.operation_date)
    ).where(
        Transaction.company_id == company_id,
        Transaction.operation_date <= history_end,
    )
    bounds = await session.execute(bounds_stmt)
    earliest_date, last_operation_date = bounds.one()

    if earliest_date is None:
        raise UnprocessableError(
            message="Нужно минимум 30 календарных дней истории",
            code="INSUFFICIENT_HISTORY",
        )

    warnings: list[str] = []
    history_start = earliest_date
    total_calendar_days = (history_end - history_start).days + 1

    if total_calendar_days < MIN_HISTORY_DAYS:
        raise UnprocessableError(
            message=f"Нужно минимум 30 календарных дней истории (найдено: {total_calendar_days})",
            code="INSUFFICIENT_HISTORY",
        )

    if total_calendar_days > MAX_HISTORY_DAYS:
        history_start = history_end - timedelta(days=MAX_HISTORY_DAYS - 1)
        warnings.append("HISTORY_TRUNCATED")

    net_sum = func.sum(
        case(
            (Transaction.direction == "inflow", Transaction.amount),
            else_=-Transaction.amount,
        )
    )

    stmt = (
        select(
            Transaction.operation_date,
            net_sum.label("net_cf"),
        )
        .where(
            Transaction.company_id == company_id,
            Transaction.operation_date >= history_start,
            Transaction.operation_date <= history_end,
        )
        .group_by(Transaction.operation_date)
        .order_by(Transaction.operation_date.asc())
    )
    result = await session.execute(stmt)
    daily_map = {row[0]: row[1] for row in result.all()}

    dense_history: list[tuple[date, Decimal]] = []
    curr = history_start
    while curr <= history_end:
        net_cf = daily_map.get(curr, Decimal("0.00"))
        dense_history.append((curr, net_cf))
        curr += timedelta(days=1)

    return dense_history, last_operation_date, warnings


async def run_forecast(
    session: AsyncSession,
    company_id: int,
    history_end: date,
    horizon_days: int,
) -> ForecastResponse:
    dense_history, last_operation_date, api_warnings = await get_dense_history_series(
        session, company_id, history_end
    )
    return await predict_history(
        dense_history, horizon_days, last_operation_date, api_warnings
    )


async def predict_history(
    dense_history: list[tuple[date, Decimal]],
    horizon_days: int,
    last_operation_date: date | None = None,
    api_warnings: list[str] | None = None,
) -> ForecastResponse:
    history_end = dense_history[-1][0]

    history_points = []
    for dt, net_cf in dense_history:
        kopecks = round(net_cf * 100)
        if kopecks > 9223372036854775807 or kopecks < -9223372036854775808:
            raise UnprocessableError(
                "Дневная сумма превышает допустимый предел для расчета прогноза"
            )
        history_points.append(
            forecast_pb2.DailyPoint(
                date=dt.isoformat(),
                net_cash_flow_minor=kopecks,
            )
        )

    request = forecast_pb2.PredictRequest(
        history=history_points,
        horizon_days=horizon_days,
    )

    channel = get_forecast_channel()
    stub = forecast_pb2_grpc.ForecastServiceStub(channel)
    logger.info(
        "gRPC stub created: ForecastServiceStub, target=%s",
        get_settings().forecast_grpc_target,
    )

    try:
        logger.info(
            "gRPC sending PredictRequest: history_days=%d, horizon_days=%d, protobuf_bytes=%d",
            len(request.history),
            horizon_days,
            request.ByteSize(),
        )
        response = await stub.Predict(request, timeout=30.0)
    except grpc.aio.AioRpcError as rpc_err:
        code = rpc_err.code()
        logger.warning("gRPC Predict failed: status=%s", code.name)
        details = rpc_err.details() or "Ошибка сервиса прогнозирования"
        if code == grpc.StatusCode.INVALID_ARGUMENT:
            raise UnprocessableError(message=details, code="INVALID_ARGUMENT")
        elif code in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.RESOURCE_EXHAUSTED):
            raise ServiceUnavailableError(
                message=f"Сервис прогнозирования временно недоступен: {details}"
            )
        elif code == grpc.StatusCode.DEADLINE_EXCEEDED:
            raise GatewayTimeoutError(
                message="Превышено время ожидания ответа от сервиса прогнозирования (30 с)"
            )
        else:
            raise BadGatewayError(
                message=f"Ошибка сервиса прогнозирования: {details}",
            )

    logger.info(
        "gRPC received PredictResponse: forecast_points=%d, model=%s, protobuf_bytes=%d",
        len(response.forecast),
        response.model_version,
        response.ByteSize(),
    )

    if len(response.forecast) != horizon_days:
        raise BadGatewayError(
            message=f"Некорректное число точек прогноза: ожидалось {horizon_days}, получено {len(response.forecast)}",
        )

    expected_date = history_end + timedelta(days=1)
    for i, pt in enumerate(response.forecast):
        if pt.date != expected_date.isoformat():
            raise BadGatewayError(
                message=f"Некорректная дата точки прогноза #{i + 1}: ожидалось {expected_date.isoformat()}, получено {pt.date}",
            )
        expected_date += timedelta(days=1)

    combined_warnings = list(dict.fromkeys([*(api_warnings or []), *response.warnings]))

    forecast_points = []
    for pt in response.forecast:
        net_decimal = Decimal(pt.net_cash_flow_minor) / Decimal(100)
        forecast_points.append(
            ForecastPoint(
                date=pt.date,
                net_cash_flow=format_decimal(net_decimal),
            )
        )

    history_start = dense_history[0][0]
    generated_at = datetime.now(UTC).isoformat()

    return ForecastResponse(
        history_end=history_end.isoformat(),
        history_start=history_start.isoformat(),
        last_operation_date=last_operation_date.isoformat()
        if last_operation_date
        else None,
        history_days=len(dense_history),
        horizon_days=horizon_days,
        model=response.model_version or "unknown",
        currency="RUB",
        generated_at=generated_at,
        warnings=combined_warnings,
        forecast=forecast_points,
    )
