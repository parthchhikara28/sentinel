from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinel"
    redis_url: str = "redis://localhost:6379/0"
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60
    stats_cache_ttl_seconds: int = 30
    worker_batch_size: int = 50
    worker_concurrency: int = 20
    worker_idle_sleep_seconds: float = 2.0
    allow_private_urls: bool = False


settings = Settings()
