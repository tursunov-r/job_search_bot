from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str
    telegram_api_id: int
    telegram_api_hash: str
    telegram_session_path: str = "data/telegram_user.session"
    telegram_channels: str = ""  # comma-separated channel usernames
    telegram_poll_interval_seconds: int = 300

    hh_search_url: str = "https://hh.ru/search/vacancy"
    hh_poll_interval_seconds: int = 600

    linkedin_enabled: bool = False
    linkedin_poll_interval_seconds: int = 3600

    vacancy_push_interval_seconds: int = 180
    ad_broadcast_check_interval_seconds: int = 1800

    database_url: str = "sqlite+aiosqlite:///data/bot.db"
    admin_telegram_user_ids: str = ""  # comma-separated

    @property
    def telegram_channel_list(self) -> list[str]:
        return [c.strip() for c in self.telegram_channels.split(",") if c.strip()]

    @property
    def admin_ids(self) -> set[int]:
        return {int(x) for x in self.admin_telegram_user_ids.split(",") if x.strip()}


settings = Settings()
