"""Supported programming languages: HH search terms + relevance detection.

Replaces the old python-only keyword_filter.py — python is now just one
entry in this registry instead of a hardcoded special case.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    key: str
    label: str
    hh_search_term: str
    keywords: tuple[str, ...]


LANGUAGES: dict[str, Language] = {
    lang.key: lang
    for lang in (
        Language("python", "Python", "python", ("python", "питон", "пайтон")),
        Language(
            "javascript",
            "JavaScript/TS",
            "javascript",
            ("javascript", "typescript", "node.js", "nodejs"),
        ),
        Language("go", "Go", "golang", ("golang", "go-разработчик", "go developer")),
        Language("java", "Java", "java", ("java",)),
    )
}

_WORD_RE_CACHE: dict[str, re.Pattern] = {}


def _keyword_pattern(keyword: str) -> re.Pattern:
    pattern = _WORD_RE_CACHE.get(keyword)
    if pattern is None:
        pattern = re.compile(rf"(?<!\w){re.escape(keyword)}(?!\w)", re.IGNORECASE)
        _WORD_RE_CACHE[keyword] = pattern
    return pattern


def _count_matches(text: str, keywords: tuple[str, ...]) -> int:
    return sum(1 for kw in keywords if _keyword_pattern(kw).search(text))


def detect_languages(title: str, description: str | None) -> list[str]:
    """Which supported languages are mentioned in this text.

    Same two-tier heuristic as the old is_python_vacancy: a match in the
    title is enough on its own, but a match only in the description needs
    at least two distinct keyword hits (avoids false positives from "nice
    to have: basic Python" postings for unrelated roles).
    """
    title = title or ""
    description = description or ""

    found = []
    for lang in LANGUAGES.values():
        if _count_matches(title, lang.keywords) >= 1:
            found.append(lang.key)
        elif _count_matches(description, lang.keywords) >= 2:
            found.append(lang.key)
    return found
