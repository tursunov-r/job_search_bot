import re

TITLE_KEYWORDS = [
    "python", "django", "flask", "fastapi", "pandas", "numpy", "pytest",
    "celery", "sqlalchemy", "pyramid", "aiohttp", "pydantic",
    "питон", "пайтон",
]

DESCRIPTION_KEYWORDS = TITLE_KEYWORDS

DENY_TITLE_PATTERNS = [
    re.compile(r"data entry", re.IGNORECASE),
    re.compile(r"\bQA\b", re.IGNORECASE),
]

_WORD_RE_CACHE: dict[str, re.Pattern] = {}


def _keyword_pattern(keyword: str) -> re.Pattern:
    pattern = _WORD_RE_CACHE.get(keyword)
    if pattern is None:
        pattern = re.compile(rf"(?<!\w){re.escape(keyword)}(?!\w)", re.IGNORECASE)
        _WORD_RE_CACHE[keyword] = pattern
    return pattern


def _count_matches(text: str, keywords: list[str]) -> int:
    return sum(1 for kw in keywords if _keyword_pattern(kw).search(text))


def is_python_vacancy(title: str, description: str) -> bool:
    title = title or ""
    description = description or ""

    if any(p.search(title) for p in DENY_TITLE_PATTERNS) and not _keyword_pattern("python").search(title):
        return False

    if _count_matches(title, TITLE_KEYWORDS) >= 1:
        return True

    if _count_matches(description, DESCRIPTION_KEYWORDS) >= 2:
        return True

    return False
