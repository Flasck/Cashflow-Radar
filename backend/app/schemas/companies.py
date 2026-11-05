from typing import Any, Literal

from pydantic import EmailStr, Field, model_validator

from app.schemas.common import StrictModel


class CompanyCreate(StrictModel):
    name: str = Field(min_length=1, max_length=160)
    industry_code: str | None = Field(default=None, max_length=50)


class CompanyUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    industry_code: str | None = Field(default=None, max_length=50)

    @model_validator(mode="before")
    @classmethod
    def check_name_not_null(cls, data: Any) -> Any:
        if isinstance(data, dict) and "name" in data and data["name"] is None:
            raise ValueError("Поле 'name' не может быть null")
        return data


class CompanyResponse(StrictModel):
    id: int
    name: str
    industry_code: str | None = None
    role: str
    last_operation_date: str | None = None


class MemberResponse(StrictModel):
    user_id: int
    company_id: int
    full_name: str
    email: str
    role: str


class UpdateMemberRoleRequest(StrictModel):
    role: Literal["treasurer", "viewer"]


class InvitationCreate(StrictModel):
    email: EmailStr
    role: Literal["treasurer", "viewer"]


class InvitationResponse(StrictModel):
    id: int
    company_id: int
    email: str
    role: str
    expires_at: str
    created_at: str | None
    status: Literal["pending", "accepted", "declined", "revoked", "expired"]
    responded_at: str | None
    token: str | None = None
    invite_url: str | None = None


class AcceptInvitationRequest(StrictModel):
    token: str = Field(min_length=1, max_length=256)


class PersonalInvitationResponse(InvitationResponse):
    company_name: str
    owner_name: str
    is_member: bool
