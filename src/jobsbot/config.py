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

    habr_poll_interval_seconds: int = 600

    geekjob_poll_interval_seconds: int = 600

    linkedin_enabled: bool = False
    linkedin_poll_interval_seconds: int = 3600

    vacancy_push_interval_seconds: int = 180
    ad_broadcast_check_interval_seconds: int = 1800

    vacancy_retention_days: int = 14
    vacancy_cleanup_interval_seconds: int = 86400

    # Optional — posting new vacancies into a group's forum topics (see
    # GroupTopic) is disabled entirely until this is set. For a private
    # supergroup this is "-100" + the internal id from a t.me/c/<id>/<n>
    # topic link (e.g. id 3880476487 -> group_chat_id -1003880476487).
    group_chat_id: int | None = None
    group_broadcast_interval_seconds: int = 180

    # Optional — the "🎯 Подготовка к интервью" button is hidden entirely
    # until this is set (no Gemini account needed to run the bot otherwise).
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"

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
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def get_db_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


settings = Settings()
