from datetime import date
from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from app.dates import get_current_moscow_date
from app.schemas.common import StrictModel


class ForecastRequest(StrictModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"history_end": "2026-11-05", "horizon_days": 7}}
    )
    history_end: date
    horizon_days: Literal[7, 30] = 30

    @field_validator("history_end")
    @classmethod
    def check_history_end(cls, v: date) -> date:
        today_msk = get_current_moscow_date()
        if v > today_msk:
            raise ValueError(
                f"Дата history_end не может быть в будущем (текущая дата: {today_msk.isoformat()})"
            )
        return v


class ForecastPoint(StrictModel):
    date: str
    net_cash_flow: str


class ForecastResponse(StrictModel):
    history_end: str
    history_start: str
    last_operation_date: str | None = None
    history_days: int
    horizon_days: int
    model: str
    currency: str = "RUB"
    generated_at: str
    warnings: list[str] = Field(default_factory=list)
    forecast: list[ForecastPoint]
