from pydantic import ConfigDict, EmailStr, Field

from app.schemas.common import StrictModel


class RegisterRequest(StrictModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(StrictModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(StrictModel):
    id: int
    full_name: str
    email: str


class VerificationRequest(StrictModel):
    email: EmailStr
    code: str = Field(pattern=r"^[0-9]{6}$")


class RegistrationResponse(StrictModel):
    email: str
    status: str = "verification_required"
