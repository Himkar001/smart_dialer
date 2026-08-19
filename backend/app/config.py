"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://smartdialer:smartdialer_pass@localhost:5432/smartdialer"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Safety Controller thresholds
    max_dial_ratio: float = 3.0
    safety_abandoned_threshold: float = 0.03
    provider_health_threshold_reject: float = 0.4
    provider_health_threshold_reduce: float = 0.7

    # Worker heartbeat
    heartbeat_interval_seconds: int = 10
    heartbeat_timeout_seconds: int = 30
    pacing_cycle_seconds: int = 2

    # Dialing behaviour
    answer_rate_window: int = 100
    wrap_up_seconds: int = 30


settings = Settings()
