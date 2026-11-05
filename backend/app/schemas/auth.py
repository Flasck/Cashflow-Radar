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


class TokenResponse(UserResponse):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(StrictModel):
    refresh_token: str = Field(min_length=1, max_length=4096)


class VerificationRequest(StrictModel):
    email: EmailStr
    code: str = Field(pattern=r"^[0-9]{6}$")


class RegistrationResponse(StrictModel):
    email: str
    status: str = "verification_required"
    retry_after: int


class ProfileUpdate(StrictModel):
    full_name: str = Field(min_length=1, max_length=120)


class AccountDeleteRequest(StrictModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    current_password: str = Field(min_length=1, max_length=128)


class PasswordChangeRequest(StrictModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class PasswordChangeConfirm(StrictModel):
    code: str = Field(pattern=r"^[0-9]{6}$")
