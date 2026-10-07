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

    # Signs login tokens. Anyone who knows it can forge a token for any user.
    secret_key: str
    access_token_minutes: int = 60

    # How long a held seat stays reserved before someone else can take it
    hold_minutes: int = 10

    redis_url: str = "redis://localhost:6379/0"
    # Run Celery tasks inline instead of sending them to Redis (used by the tests)
    celery_task_always_eager: bool = False

    # Browser origins allowed to call the API: the Next.js front end in Compose
    # (port 3100) and when run directly with `npm run dev` (port 3000).
    # Set as a JSON list, e.g. CORS_ORIGINS='["https://slotwise.example.com"]'
    cors_origins: list[str] = ["http://localhost:3100", "http://localhost:3000"]


settings = Settings()
