from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


def format_decimal(value: Decimal | None) -> str:
    if value is None:
        return "0.00"
    return f"{value:.2f}"
