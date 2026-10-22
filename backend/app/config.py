from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env", BASE_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_user: str = "cashflow"
    postgres_password: str = "cashflow_dev_password"
    postgres_host: str = "localhost"
    postgres_port: int = 5433
    postgres_db: str = "cashflow_radar"

    jwt_secret_key: str = "change-this-development-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    database_url_custom: str | None = Field(default=None, alias="database_url")

    @property
    def database_url(self) -> str:
        if self.database_url_custom:
            return self.database_url_custom
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
