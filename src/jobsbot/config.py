from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str
    telegram_api_id: int
    telegram_api_hash: str
    telegram_session_path: str = "data/telegram_user.session"
    telegram_poll_interval_seconds: int = 300

    hh_search_url: str = "https://hh.ru/search/vacancy"
    hh_poll_interval_seconds: int = 600

    linkedin_enabled: bool = False
    linkedin_poll_interval_seconds: int = 3600

    vacancy_push_interval_seconds: int = 180
    ad_broadcast_check_interval_seconds: int = 1800

    database_url: str = "sqlite+aiosqlite:///data/bot.db"
    super_admin_telegram_user_id: int


settings = Settings()
