from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, read from environment variables (case-insensitive).

    Each field below maps to an env var of the same name, e.g. DATABASE_URL.
    A field without a default is required: the app refuses to start without it.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Slotwise"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://slotwise:slotwise@localhost:5433/slotwise"


settings = Settings()
