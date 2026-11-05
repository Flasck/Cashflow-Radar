import json
from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://radar:radar@localhost:55432/cashflow_radar",
        validation_alias=AliasChoices("RADAR_DATABASE_URL", "DATABASE_URL"),
    )
    jwt_secret: str = Field(
        validation_alias="RADAR_JWT_SECRET",
        min_length=32,
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=15, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)

    smtp_host: str = Field(default="smtp.mail.ru", validation_alias="RADAR_SMTP_HOST")
    smtp_port: int = Field(
        default=465, validation_alias="RADAR_SMTP_PORT", ge=1, le=65535
    )
    smtp_user: str = Field(default="", validation_alias="RADAR_SMTP_USER")
    smtp_password: SecretStr = Field(
        default=SecretStr(""), validation_alias="RADAR_SMTP_PASSWORD"
    )

    allowed_origins_raw: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("RADAR_ALLOWED_ORIGINS", "ALLOWED_ORIGINS"),
    )

    forecast_grpc_target: str = Field(
        default="localhost:50051",
        validation_alias=AliasChoices(
            "FORECAST_GRPC_TARGET", "RADAR_FORECAST_GRPC_TARGET"
        ),
    )

    @property
    def allowed_origins(self) -> list[str]:
        raw = self.allowed_origins_raw.strip()
        if not raw:
            return ["http://localhost:3000"]
        if raw.startswith("[") and raw.endswith("]"):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except json.JSONDecodeError:
                pass
        return [part.strip() for part in raw.split(",") if part.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
