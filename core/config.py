"""Central configuration, loaded from environment variables (.env in dev).

No secret ever has a hardcoded default that would work in production — BOT_TOKEN
and SECRET_KEY must be supplied by the environment.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"
    log_level: str = "INFO"

    secret_key: str
    bot_token: str = ""
    bot_username: str = "shivirbot"
    web_base_url: str = "http://localhost:8000"

    database_url: str = "sqlite+aiosqlite:///./shivir_dev.db"
    redis_url: str = "redis://localhost:6379/0"

    rate_limit_send_per_fingerprint: int = 5
    rate_limit_send_per_fingerprint_window_seconds: int = 300
    rate_limit_send_per_link: int = 30
    rate_limit_send_per_link_window_seconds: int = 300
    rate_limit_send_global: int = 2000
    rate_limit_send_global_window_seconds: int = 60

    link_auto_disable_report_threshold: int = 5

    # Comma-separated Telegram user IDs allowed to use moderation-queue bot commands.
    # V1 has no separate admin web dashboard (that's V2+); the queue is reviewed via
    # bot commands restricted to this allowlist.
    admin_tg_user_ids: str = ""

    @property
    def admin_ids(self) -> set[int]:
        return {int(x) for x in self.admin_tg_user_ids.split(",") if x.strip()}

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
