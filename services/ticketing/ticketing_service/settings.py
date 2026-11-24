from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg://ticketing:local-ticketing-only@ticketing-db:5432/ticketing"
    )
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
