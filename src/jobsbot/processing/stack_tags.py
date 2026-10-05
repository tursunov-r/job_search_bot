"""User-selectable stack tags (frameworks/DB/queues) for vacancy filtering."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class StackTag:
    key: str
    label: str
    keywords: tuple[str, ...]


STACK_TAGS: dict[str, StackTag] = {
    tag.key: tag
    for tag in (
        StackTag("django", "Django", ("django",)),
        StackTag("flask", "Flask", ("flask",)),
        StackTag("fastapi", "FastAPI", ("fastapi",)),
        StackTag("celery", "Celery", ("celery",)),
        StackTag("pandas", "Pandas/NumPy", ("pandas", "numpy")),
        StackTag("postgresql", "PostgreSQL", ("postgresql", "postgres")),
        StackTag("mysql", "MySQL", ("mysql",)),
        StackTag("mongodb", "MongoDB", ("mongodb", "mongo")),
        StackTag("redis", "Redis", ("redis",)),
        StackTag("rabbitmq", "RabbitMQ", ("rabbitmq", "amqp")),
        StackTag("kafka", "Kafka", ("kafka",)),
        StackTag("docker", "Docker/K8s", ("docker", "kubernetes", "k8s")),
    )
}

# Layout for the inline keyboard: rows of tag keys.
STACK_TAG_ROWS: list[list[str]] = [
    ["django", "flask"],
    ["fastapi", "celery"],
    ["pandas", "postgresql"],
    ["mysql", "mongodb"],
    ["redis", "rabbitmq"],
    ["kafka", "docker"],
]

_WORD_RE_CACHE: dict[str, re.Pattern] = {}


def _keyword_pattern(keyword: str) -> re.Pattern:
    pattern = _WORD_RE_CACHE.get(keyword)
    if pattern is None:
        pattern = re.compile(rf"(?<!\w){re.escape(keyword)}(?!\w)", re.IGNORECASE)
        _WORD_RE_CACHE[keyword] = pattern
    return pattern


def matches_stack(title: str, description: str | None, selected_keys: list[str]) -> bool:
    """No tags selected = no filter (everything matches). Otherwise match if
    any keyword from any selected tag appears in title+description."""
    if not selected_keys:
        return True

    text = f"{title or ''} {description or ''}"
    for key in selected_keys:
        tag = STACK_TAGS.get(key)
        if tag is None:
            continue
        if any(_keyword_pattern(kw).search(text) for kw in tag.keywords):
            return True

    return False
