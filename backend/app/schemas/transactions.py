from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransactionSplitCreate(BaseModel):
    category_id: int = Field(gt=0)
    allocated_amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)


class TransactionCreate(BaseModel):
    operation_date: date
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    direction: Literal["inflow", "outflow"]
    purpose: str | None = None
    splits: list[TransactionSplitCreate] = Field(min_length=1)

    @field_validator("splits")
    @classmethod
    def check_unique_categories(
        cls, value: list[TransactionSplitCreate]
    ) -> list[TransactionSplitCreate]:
        category_ids = [split.category_id for split in value]
        if len(category_ids) != len(set(category_ids)):
            raise ValueError("Each category can appear only once in splits")
        return value


class TransactionUpdate(BaseModel):
    purpose: str | None


class TransactionSplitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_id: int
    allocated_amount: Decimal


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    operation_date: date
    amount: Decimal
    direction: str
    purpose: str | None
    splits: list[TransactionSplitResponse]
