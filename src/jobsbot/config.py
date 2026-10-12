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

    # A vacancy whose *real* publish date (parsed from the source site) is
    # already older than this by the time our scraper first discovers it
    # is held back from delivery — see repo.py::_freshness_clause().
    vacancy_freshness_days: int = 3

    # Consecutive polling cycles with zero raw results (not zero *new*
    # vacancies — that's normal) before alerting the super admin that a
    # scraper adapter might be broken. See storage.models.AdapterHealth.
    adapter_failure_threshold: int = 3

    # When the weekly digest (push.py::send_weekly_digest) fires — APScheduler
    # cron fields, server-local time.
    weekly_digest_day_of_week: str = "mon"
    weekly_digest_hour: int = 10

    # Single reference timezone all subscribers' "🌙 Тихие часы" are
    # interpreted in — not per-subscriber (that would need a timezone
    # picker, a much bigger feature), just the primary market's zone.
    bot_timezone: str = "Asia/Almaty"

    # Web admin panel (FastAPI, separate "web" service/container) — single
    # shared HTTP Basic credential pair, no per-staff roles yet (that's a
    # deliberate v1 simplification, same trade-off as everywhere else that
    # starts simple and gets layered later if needed).
    #
    # Deliberately NOT required (unlike bot_token/db_password): this one
    # Settings object is imported by the bot process too, which doesn't
    # use it at all — a missing env var here must never crash the bot.
    # The default is a placeholder, not a real credential — change it in
    # .env before relying on it for anything.
    web_admin_username: str = "admin"
    web_admin_password: str = "change-me"
    web_port: int = 8000

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
    gemini_model: str = "gemini-3.8-flash"

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
