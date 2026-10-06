from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", env_ignore_empty=True
    )

    bot_token: str

    # Optional — Telegram channel parsing (Telethon) is entirely disabled
    # until both are set. Needs a personal Telegram account's API
    # credentials from my.telegram.org, not the bot's own token.
    telegram_api_id: int | None = None
    telegram_api_hash: str | None = None
    telegram_session_path: str = "data/telegram_user.session"
    telegram_poll_interval_seconds: int = 300

    hh_search_url: str = "https://hh.ru/search/vacancy"
    hh_poll_interval_seconds: int = 600

    linkedin_enabled: bool = False
    linkedin_poll_interval_seconds: int = 3600

    vacancy_push_interval_seconds: int = 180
    ad_broadcast_check_interval_seconds: int = 1800

    db_host: str = "postgres"
    db_port: int = 5432
    db_name: str = "jobsbot"
    db_user: str = "jobsbot"
    db_password: str

    super_admin_telegram_user_id: int

    @property
    def telegram_enabled(self) -> bool:
        return self.telegram_api_id is not None and bool(self.telegram_api_hash)

    @property
    def get_db_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


settings = Settings()
