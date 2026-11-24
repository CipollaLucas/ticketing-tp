"""Service-owned configuration. A service credential is mandatory for introspection."""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")
    database_url: str = "postgresql+psycopg://identity:local-identity-only@identity-db:5432/identity"
    session_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    identity_internal_token: str = Field(min_length=32)


settings = Settings()
