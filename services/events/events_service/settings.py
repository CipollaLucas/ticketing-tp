from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://events:local-events-only@events-db:5432/events"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
