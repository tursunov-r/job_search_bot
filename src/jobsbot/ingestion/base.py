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
    posted_at: datetime | None = None
