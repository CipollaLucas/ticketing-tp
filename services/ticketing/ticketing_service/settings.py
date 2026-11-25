from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg://ticketing:local-ticketing-only@ticketing-db:5432/ticketing"
    )
    sale_commands_enabled: bool = False
    events_internal_token: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
