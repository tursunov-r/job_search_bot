"""Canonical work-format categories a subscriber can filter by, and how to
tell which ones a vacancy's free-text work_format field actually offers.

Sources never give a clean enum here — HH/Habr write free text like
"удалённо или гибрид" or "на месте работодателя" — so matching is by
substring, and a single vacancy can land in more than one category at once
(e.g. an employer offering either office or remote)."""

WORK_FORMATS: dict[str, str] = {
    "remote": "🏠 Удалённо",
    "office": "🏢 Офис",
    "hybrid": "🔀 Гибрид",
}


def categorize(work_format_text: str | None) -> set[str]:
    text = (work_format_text or "").lower()
    categories = set()
    if "удал" in text:
        categories.add("remote")
    if "гибрид" in text:
        categories.add("hybrid")
    if "на месте" in text or "офис" in text:
        categories.add("office")
    return categories
