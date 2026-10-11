"""Parses a minimum RUB salary figure out of a source's free-text salary
string, for the subscriber-facing salary filter (see push.py::_matches_salary).

Real salary_text samples seen in production: "до 100 000 ₽", "от 100 000
до 130 000 ₽", "60 000 ₽ за месяц на руки", "от 500 до 3 500 $ за месяц на
руки", "от 2 500 до 3 000 Br за месяц до вычета налогов", "от 5 000 000 до
10 000 000 so'm за месяц на руки". Only ₽ figures are parsed — comparing
across currencies would need a maintained exchange rate, which isn't worth
it for a coarse "at least X" filter; non-RUB vacancies are treated as
"unknown" (None) rather than guessed at.

A "до Y ₽" (up to Y, no stated floor) also comes back None rather than 0 —
we genuinely don't know the floor, and both callers here treat None as
"don't exclude this one" (fail open), same reasoning as the freshness and
subscription-gate filters elsewhere in this codebase.
"""

import re

_NUMBER_RE = re.compile(r"\d[\d\s]*\d|\d")


def parse_salary_min_rub(salary_text: str | None) -> int | None:
    if not salary_text or "₽" not in salary_text:
        return None

    normalized = salary_text.replace("\xa0", " ").strip()
    if normalized.lower().startswith("до"):
        return None

    numbers = [int(re.sub(r"\s", "", match)) for match in _NUMBER_RE.findall(normalized)]
    return min(numbers) if numbers else None
