from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg://ticketing:local-ticketing-only@ticketing-db:5432/ticketing"
    )
    sale_commands_enabled: bool = False
    gate_provisioning_enabled: bool = False
    purchases_enabled: bool = False
    zone_configuration_enabled: bool = False
    identity_service_url: str = "http://identity:8001"
    events_service_url: str = "http://events:8002"
    identity_internal_token: str = ""
    purchase_timeout_seconds: float = 2.0
    events_internal_token: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
