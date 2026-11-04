from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.common import StrictModel


def validate_positive_two_decimals(v: Decimal | None) -> Decimal | None:
    if v is None:
        return None
    if not v.is_finite():
        raise ValueError("Сумма должна быть конечным числом")
    if v <= 0:
        raise ValueError("Сумма должна быть строго положительной")
    exp = v.as_tuple().exponent
    if isinstance(exp, int) and exp < -2:
        raise ValueError("Сумма не должна содержать более двух знаков после запятой")
    if v > Decimal("9999999999999.99"):
        raise ValueError("Сумма превышает максимально допустимый предел")
    return v


class TransactionCreate(StrictModel):
    operation_date: date
    amount: Decimal
    direction: Literal["inflow", "outflow"]
    category_id: int | None = None
    purpose: str | None = Field(default=None, max_length=500)

    @field_validator("amount")
    @classmethod
    def check_amount(cls, v: Decimal) -> Decimal:
        val = validate_positive_two_decimals(v)
        assert val is not None
        return val


class TransactionUpdate(StrictModel):
    operation_date: date | None = None
    amount: Decimal | None = None
    direction: Literal["inflow", "outflow"] | None = None
    category_id: int | None = None
    purpose: str | None = Field(default=None, max_length=500)

    @model_validator(mode="before")
    @classmethod
    def check_mandatory_fields_not_null(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for field in ("operation_date", "amount", "direction"):
                if field in data and data[field] is None:
                    raise ValueError(
                        f"Поле '{field}' не может быть null при обновлении"
                    )
        return data

    @field_validator("amount")
    @classmethod
    def check_amount(cls, v: Decimal | None) -> Decimal | None:
        return validate_positive_two_decimals(v)


class TransactionResponse(StrictModel):
    id: int
    company_id: int
    operation_date: str
    amount: str
    direction: str
    category_id: int | None = None
    category_name: str | None = None
    purpose: str | None = None


class TransactionListResponse(StrictModel):
    items: list[TransactionResponse]
    total: int
    page: int
    page_size: int
