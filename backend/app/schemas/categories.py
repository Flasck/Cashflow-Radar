from pydantic import Field

from app.schemas.common import StrictModel


class CategoryCreate(StrictModel):
    name: str = Field(min_length=1, max_length=100)


class CategoryUpdate(StrictModel):
    name: str = Field(min_length=1, max_length=100)


class CategoryResponse(StrictModel):
    id: int
    company_id: int
    name: str
