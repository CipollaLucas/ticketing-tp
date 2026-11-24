from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://events:local-events-only@events-db:5432/events"
    protected_drafts_enabled: bool = False
    identity_service_url: str = ""
    identity_internal_token: str = ""
    identity_timeout_seconds: float = 2.0
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
