from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawVacancy:
    title: str
    description: str | None
    url: str | None
    company: str | None = None
    salary_text: str | None = None
    location: str | None = None
    work_format: str | None = None  # remote / office / hybrid, as stated by the source
    experience: str | None = None
    employment_type: str | None = None
    schedule: str | None = None
    posted_at: datetime | None = None
    source_chat_id: int | None = None  # set by telegram_listener, for forwarding the original message
    source_message_id: int | None = None
