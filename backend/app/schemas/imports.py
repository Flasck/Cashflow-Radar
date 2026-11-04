from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator

from app.dates import get_current_moscow_date
from app.schemas.common import StrictModel
from app.schemas.transactions import validate_positive_two_decimals


class ImportPreviewError(StrictModel):
    row_number: int
    column: str | None = None
    message: str


class PreviewRow(StrictModel):
    row_number: int
    operation_date: str | None = None
    amount: str | None = None
    direction: str = ""
    category: str | None = None
    purpose: str | None = None
    is_valid: bool
    errors: list[str] = Field(default_factory=list)


class PreviewSummary(StrictModel):
    total_rows: int
    valid_rows: int
    error_rows: int
    date_from: str | None = None
    date_to: str | None = None
    total_inflow: str = "0.00"
    total_outflow: str = "0.00"
    total_net: str = "0.00"


class PreviewResponse(StrictModel):
    rows: list[PreviewRow]
    errors: list[ImportPreviewError]
    new_categories: list[str]
    summary: PreviewSummary
    can_commit: bool


class CommitRow(StrictModel):
    operation_date: date
    amount: Decimal
    direction: Literal["inflow", "outflow"]
    category: str | None = None
    purpose: str | None = Field(default=None, max_length=500)

    @field_validator("operation_date")
    @classmethod
    def check_operation_date(cls, v: date) -> date:
        today_msk = get_current_moscow_date()
        if v > today_msk:
            raise ValueError(
                f"Дата операции не может быть в будущем (текущая дата: {today_msk.isoformat()})"
            )
        return v

    @field_validator("amount")
    @classmethod
    def check_amount(cls, v: Decimal) -> Decimal:
        val = validate_positive_two_decimals(v)
        assert val is not None
        return val


class CommitRequest(StrictModel):
    rows: list[CommitRow]


class CommitResponse(StrictModel):
    imported_count: int
    created_categories_count: int
