"""Application settings, loaded from environment variables / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    # --- General ---
    ENV: str = "dev"
    DEBUG: bool = True
    # Public HTTPS origin of this API. Telegram will call {BASE_URL}/webhook/... so in
    # local development this must be a tunnel (ngrok / cloudflared), not localhost.
    BASE_URL: str = "http://localhost:8000"
    # Where the SPA lives; used for CORS and for deep links inside HR notifications.
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://talento:talento@localhost:5432/talento"

    # --- Redis (FSM state, token cache, rate limiting, Celery broker) ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Auth ---
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_TTL_MINUTES: int = 15
    REFRESH_TOKEN_TTL_DAYS: int = 30

    # --- Bot token encryption (AES-256-GCM) ---
    # 32 raw bytes, base64/urlsafe-encoded. Generate with:
    #   python -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
    BOT_TOKEN_ENCRYPTION_KEY: str = "dev-only-key-do-not-use-in-production-32b"

    # --- Platform service bot (HR notifications, /link flow) ---
    PLATFORM_BOT_TOKEN: str = ""
    PLATFORM_BOT_USERNAME: str = ""

    # --- Files (S3 / MinIO) ---
    S3_ENDPOINT_URL: str | None = None
    S3_BUCKET: str = "talento"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = "us-east-1"
    S3_PUBLIC_URL: str | None = None
    # When S3 is not configured, uploaded candidate files land here instead.
    LOCAL_UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024

    # --- Observability ---
    SENTRY_DSN: str = ""
    LOG_LEVEL: str = "INFO"

    # --- Limits ---
    DEFAULT_LANGUAGE: str = "ru"
    FSM_TTL_SECONDS: int = 60 * 60 * 24
    BOT_TOKEN_CACHE_SECONDS: int = 600

    @property
    def celery_broker_url(self) -> str:
        return self.REDIS_URL

    @property
    def sync_database_url(self) -> str:
        """Alembic and Celery use the sync driver."""
        return self.DATABASE_URL.replace("+asyncpg", "").replace(
            "postgresql://", "postgresql+psycopg2://"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
