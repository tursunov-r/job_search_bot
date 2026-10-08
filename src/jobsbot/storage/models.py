import uuid as uuid_lib
from datetime import datetime, timezone

from sqlalchemy import BigInteger
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
    uuid: str = Field(default_factory=lambda: str(uuid_lib.uuid4()), index=True, unique=True)
    fingerprint: str = Field(index=True, unique=True)
    title: str
    company: str | None = None
    description: str | None = None
    url: str | None = None
    source_id: int = Field(foreign_key="sources.id")
    raw_source_ids: str = Field(default="[]")  # JSON array of source_ids (cross-post tracking)
    salary_text: str | None = None
    location: str | None = None
    work_format: str | None = None  # remote / office / hybrid, as stated by the source
    experience: str | None = None
    employment_type: str | None = None
    schedule: str | None = None
    posted_at: datetime | None = Field(default=None, index=True)
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_python_relevant: bool = True
    languages: str = Field(default="[]")  # JSON array of languages.py keys detected/assigned
    # Telegram chat ids (esp. channels/supergroups) routinely exceed int32 —
    # plain int here maps to a Postgres INTEGER and would silently reject them.
    source_chat_id: int | None = Field(default=None, sa_type=BigInteger)  # for forwarding the original message
    source_message_id: int | None = None  # Telegram message id, for forwarding the original message
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # False only while a later detail-page enrichment pass (HH/Habr) is
    # still pending — push_new_vacancies skips a vacancy until this is True
    # (or it's old enough that the enrichment pass must have already run
    # and failed), so subscribers never get a message missing fields that
    # simply hadn't been fetched yet.
    details_checked: bool = True
    # Set the moment a subscriber reports it — excluded from delivery to
    # anyone else until an admin with "moderate_vacancies" resolves the
    # report (keep it visible again, or leave it permanently hidden).
    hidden: bool = False


class Subscriber(SQLModel, table=True):
    __tablename__ = "subscribers"

    id: int | None = Field(default=None, primary_key=True)
    # Modern Telegram user ids routinely exceed int32 (e.g. 8419696219) —
    # plain int here maps to a Postgres INTEGER and silently rejects them,
    # so most real users could never even get a Subscriber row created.
    telegram_user_id: int = Field(index=True, unique=True, sa_type=BigInteger)
    username: str | None = None
    status: str = "active"  # 'active', 'paused', 'blocked'
    subscribed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_vacancy_sent_id: int | None = Field(default=None, foreign_key="vacancies.id")
    last_interaction_at: datetime | None = None
    skills: str = Field(default="[]")  # JSON array of stack_tags keys the subscriber selected
    languages: str = Field(default="[]")  # JSON array of languages.py keys the subscriber selected
    city: str | None = None  # free-text, matched against Vacancy.location; None = no city filter
    work_formats: str = Field(default="[]")  # JSON array of work_formats.py keys; [] = no filter


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


class VacancyReport(SQLModel, table=True):
    """A subscriber's complaint about a vacancy, with a mandatory comment —
    created the moment they report it (which also immediately hides the
    vacancy, see Vacancy.hidden), resolved later by an admin."""

    __tablename__ = "vacancy_reports"

    id: int | None = Field(default=None, primary_key=True)
    vacancy_id: int = Field(foreign_key="vacancies.id", index=True)
    subscriber_id: int = Field(foreign_key="subscribers.id")
    comment: str
    status: str = "pending"  # 'pending', 'resolved_removed', 'resolved_kept'
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_by_telegram_user_id: int | None = Field(default=None, sa_type=BigInteger)
    resolved_at: datetime | None = None


class StaffMember(SQLModel, table=True):
    """Staff added by the super admin via the bot, with per-action
    permissions (see bot/permissions.py). The super admin itself isn't a
    row here — it's a single hardcoded telegram_user_id from .env."""

    __tablename__ = "staff_members"

    id: int | None = Field(default=None, primary_key=True)
    telegram_user_id: int = Field(index=True, unique=True, sa_type=BigInteger)
    username: str | None = None
    permissions: str = Field(default="[]")  # JSON array of bot/permissions.py keys
    added_by_telegram_user_id: int = Field(sa_type=BigInteger)
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


class GroupTopic(SQLModel, table=True):
    """Maps a languages.py key to a forum-topic thread id in the group
    configured via GROUP_CHAT_ID — managed in the DB (not .env) since it's
    operational data that can change without a redeploy, same reasoning as
    Telegram channels/staff. More than one language can share a thread_id
    (e.g. all mobile languages posting into one "Mobile" topic)."""

    __tablename__ = "group_topics"

    language_key: str = Field(primary_key=True)
    thread_id: int


class GroupTopicPost(SQLModel, table=True):
    """One row per (vacancy, thread) actually posted to a group topic — the
    de-dup record so a vacancy stays a single post per topic even if more
    than one of its languages maps to the same thread_id (e.g. a vacancy
    tagged both "kotlin" and "swift" when both share one "Mobile" topic
    wouldn't otherwise be told that's the same destination), and reruns/
    restarts don't double-post."""

    __tablename__ = "group_topic_posts"
    __table_args__ = (UniqueConstraint("vacancy_id", "thread_id"),)

    id: int | None = Field(default=None, primary_key=True)
    vacancy_id: int = Field(foreign_key="vacancies.id", index=True)
    thread_id: int
    posted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
