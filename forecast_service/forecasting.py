import datetime
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from contracts.forecast_pb2 import DailyPoint

MODEL_VERSION = "mean-7d-1.0.0"
MIN_HISTORY_DAYS = 30
MAX_HISTORY_DAYS = 1825
ALLOWED_HORIZONS = {7, 30}


def validate_history_and_horizon(
    history: Sequence[DailyPoint],
    horizon_days: int,
) -> tuple[list[datetime.date], list[int], list[str]]:
    if len(history) < MIN_HISTORY_DAYS or len(history) > MAX_HISTORY_DAYS:
        raise ValueError(
            f"History length must be between {MIN_HISTORY_DAYS} and {MAX_HISTORY_DAYS} "
            f"calendar days, got {len(history)}"
        )

    if horizon_days not in ALLOWED_HORIZONS:
        raise ValueError(f"horizon_days must be 7 or 30, got {horizon_days}")

    try:
        parsed_dates = [datetime.date.fromisoformat(point.date) for point in history]
    except ValueError:
        raise ValueError("Invalid date format. Expected YYYY-MM-DD") from None

    for index, day in enumerate(parsed_dates):
        if history[index].date != day.isoformat():
            raise ValueError("Invalid date format. Expected strict YYYY-MM-DD")
        if day != parsed_dates[0] + datetime.timedelta(days=index):
            raise ValueError("History dates must be strictly consecutive calendar days")

    minor_values = [point.net_cash_flow_minor for point in history]

    warnings: list[str] = []
    if len(history) < 90:
        warnings.append("SHORT_HISTORY")

    nonzero_count = sum(1 for v in minor_values if v != 0)
    if nonzero_count < 10:
        warnings.append("SPARSE_HISTORY")

    if len(set(minor_values)) <= 1:
        warnings.append("CONSTANT_HISTORY")

    return parsed_dates, minor_values, warnings


def run_forecast(
    history_dates: Sequence[datetime.date],
    history_minor: Sequence[int],
    horizon_days: int,
) -> list[tuple[str, int]]:
    last_week = history_minor[-7:]
    average = Decimal(sum(last_week)) / len(last_week)
    amount = int(average.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return [
        ((history_dates[-1] + datetime.timedelta(days=day)).isoformat(), amount)
        for day in range(1, horizon_days + 1)
    ]
