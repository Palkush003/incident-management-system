"""
Application configuration — powered by pydantic-settings.
All values are read from environment variables or the .env file.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str = "development"
    app_port: int = 8000
    secret_key: str = "change-me-in-production"

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    postgres_user: str = "ims_user"
    postgres_password: str = "ims_secret_2024"
    postgres_db: str = "ims_db"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ── MongoDB ───────────────────────────────────────────────────────────────
    mongo_user: str = "ims_user"
    mongo_password: str = "ims_secret_2024"
    mongo_host: str = "localhost"
    mongo_port: int = 27017
    mongo_db: str = "ims_signals"

    @property
    def mongo_url(self) -> str:
        return f"mongodb://{self.mongo_user}:{self.mongo_password}@{self.mongo_host}:{self.mongo_port}"

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = "ims_redis_2024"
    redis_db: int = 0

    @property
    def redis_url(self) -> str:
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # ── Kafka ─────────────────────────────────────────────────────────────────
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group: str = "ims-processors"
    kafka_raw_signals_topic: str = "raw-signals"
    kafka_processed_topic: str = "processed-incidents"
    kafka_alert_topic: str = "alert-events"

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    rate_limit_requests: int = 10000
    rate_limit_window_seconds: int = 1

    # ── Debounce ──────────────────────────────────────────────────────────────
    debounce_window_seconds: int = 10
    debounce_threshold: int = 100

    # ── Memory Buffer ─────────────────────────────────────────────────────────
    memory_buffer_size: int = 50000

    # ── Metrics ───────────────────────────────────────────────────────────────
    metrics_interval_seconds: int = 5

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
