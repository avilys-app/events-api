"""Application settings, loaded from the environment."""

from enum import StrEnum
from functools import lru_cache

from pydantic import EmailStr, Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Environment.DEVELOPMENT
    port: int = 3000

    db_host: str = "localhost"
    db_port: int = 5432
    db_username: str = "postgres"
    db_password: SecretStr = SecretStr("")
    db_name: str = "events"

    jwt_secret: SecretStr
    jwt_expires_in: str = Field(default="7d", pattern=r"^\d+[dhms]$")

    resend_api_key: SecretStr = SecretStr("")
    email_from: str = "Events <onboarding@resend.dev>"
    email_confirmation_url: str = "http://localhost:3000/confirm-email"
    email_confirmation_expires_in: str = Field(default="24h", pattern=r"^\d+[dhms]$")
    email_resend_cooldown: str = Field(default="60s", pattern=r"^\d+[dhms]$")
    email_outbox_worker_enabled: bool = True
    email_outbox_poll_interval: str = Field(default="5s", pattern=r"^\d+[dhms]$")

    report_to_email: EmailStr | None = None

    @field_validator("report_to_email", mode="before")
    @classmethod
    def empty_report_email_is_missing(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def database_dsn(self) -> PostgresDsn:
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.db_username,
            password=self.db_password.get_secret_value() or None,
            host=self.db_host,
            port=self.db_port,
            path=self.db_name,
        )

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    @property
    def echo_sql(self) -> bool:
        return self.environment is Environment.DEVELOPMENT

    @property
    def uses_supabase_pooler(self) -> bool:
        """Whether the database host is Supabase's PgBouncer/Supavisor endpoint."""
        return self.db_host.casefold().endswith(".pooler.supabase.com")


@lru_cache
def get_settings() -> Settings:
    """Cached so the environment is read once per process."""
    return Settings()
