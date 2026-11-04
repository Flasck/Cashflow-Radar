from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Category name must not be empty")
        return value


class CategoryUpdate(CategoryCreate):
    pass
