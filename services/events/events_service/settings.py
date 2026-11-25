from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://events:local-events-only@events-db:5432/events"
    protected_drafts_enabled: bool = False
    gate_provisioning_enabled: bool = False
    publication_enabled: bool = False
    unpublication_enabled: bool = False
    ticketing_service_url: str = ""
    ticketing_internal_token: str = ""
    ticketing_timeout_seconds: float = 2.0
    identity_service_url: str = ""
    identity_internal_token: str = ""
    identity_timeout_seconds: float = 2.0
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
