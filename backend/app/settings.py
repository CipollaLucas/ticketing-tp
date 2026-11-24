from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://ticketing:local-dev-only@db:5432/ticketing"
    session_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    identity_canary_enabled: bool = False
    identity_service_url: str = ""
    identity_internal_token: str = ""
    identity_timeout_seconds: float = Field(default=2.0, gt=0, le=10)
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
