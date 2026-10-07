from datetime import datetime, timezone

from sqlmodel import SQLModel, Field, UniqueConstraint


class Source(SQLModel, table=True):
    __tablename__ = "sources"

    id: int | None = Field(default=None, primary_key=True)
    type: str  # 'hh', 'telegram_channel', 'linkedin'
    identifier: str  # channel username, or a constant like 'hh_search'
    display_name: str | None = None
    enabled: bool = True
    poll_interval_seconds: int | None = None  # null for event-driven sources
    last_polled_at: datetime | None = None
    last_message_id: int | None = None  # telegram_channel cursor for get_messages(min_id=...)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Vacancy(SQLModel, table=True):
    __tablename__ = "vacancies"

    id: int | None = Field(default=None, primary_key=True)
    fingerprint: str = Field(index=True, unique=True)
    title: str
    company: str | None = None
    description: str | None = None
    url: str | None = None
    source_id: int = Field(foreign_key="sources.id")
    raw_source_ids: str = Field(default="[]")  # JSON array of source_ids (cross-post tracking)
    salary_text: str | None = None
    location: str | None = None
    posted_at: datetime | None = Field(default=None, index=True)
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_python_relevant: bool = True
    languages: str = Field(default="[]")  # JSON array of languages.py keys detected/assigned
    source_chat_id: int | None = None  # Telegram chat id, for forwarding the original message
    source_message_id: int | None = None  # Telegram message id, for forwarding the original message
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Subscriber(SQLModel, table=True):
    __tablename__ = "subscribers"

    id: int | None = Field(default=None, primary_key=True)
    telegram_user_id: int = Field(index=True, unique=True)
    username: str | None = None
    status: str = "active"  # 'active', 'paused', 'blocked'
    subscribed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_vacancy_sent_id: int | None = Field(default=None, foreign_key="vacancies.id")
    last_interaction_at: datetime | None = None
    skills: str = Field(default="[]")  # JSON array of stack_tags keys the subscriber selected
    languages: str = Field(default="[]")  # JSON array of languages.py keys the subscriber selected


class VacancyDelivery(SQLModel, table=True):
    """One row per vacancy actually delivered to a subscriber — lets us
    safely re-scan old vacancies after a profile change without
    re-sending ones already delivered (the cursor alone can't tell us that,
    since it only tracks "considered", not "sent")."""

    __tablename__ = "vacancy_deliveries"
    __table_args__ = (UniqueConstraint("subscriber_id", "vacancy_id"),)

    id: int | None = Field(default=None, primary_key=True)
    subscriber_id: int = Field(foreign_key="subscribers.id", index=True)
    vacancy_id: int = Field(foreign_key="vacancies.id", index=True)
    delivered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StaffMember(SQLModel, table=True):
    """Staff added by the super admin via the bot, with per-action
    permissions (see bot/permissions.py). The super admin itself isn't a
    row here — it's a single hardcoded telegram_user_id from .env."""

    __tablename__ = "staff_members"

    id: int | None = Field(default=None, primary_key=True)
    telegram_user_id: int = Field(index=True, unique=True)
    username: str | None = None
    permissions: str = Field(default="[]")  # JSON array of bot/permissions.py keys
    added_by_telegram_user_id: int
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "active"  # 'active', 'removed'


class AdCampaign(SQLModel, table=True):
    __tablename__ = "ad_campaigns"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    message_text: str
    media_file_id: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    send_interval_hours: int | None = None
    status: str = "draft"  # 'draft','active','completed','cancelled'
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AdImpression(SQLModel, table=True):
    __tablename__ = "ad_impressions"

    id: int | None = Field(default=None, primary_key=True)
    campaign_id: int = Field(foreign_key="ad_campaigns.id")
    subscriber_id: int = Field(foreign_key="subscribers.id")
    sent_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    delivery_status: str = "sent"  # 'sent','failed','blocked'
