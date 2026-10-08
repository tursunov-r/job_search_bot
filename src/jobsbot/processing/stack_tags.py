"""User-selectable stack tags (frameworks/DB/queues) for vacancy filtering."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class StackTag:
    key: str
    label: str
    keywords: tuple[str, ...]
    language: str | None = None  # None = universal (DB/queue/infra), else a languages.py key


STACK_TAGS: dict[str, StackTag] = {
    tag.key: tag
    for tag in (
        StackTag("django", "Django", ("django",), language="python"),
        StackTag("flask", "Flask", ("flask",), language="python"),
        StackTag("fastapi", "FastAPI", ("fastapi",), language="python"),
        StackTag("celery", "Celery", ("celery",), language="python"),
        StackTag("pandas", "Pandas/NumPy", ("pandas", "numpy"), language="python"),
        StackTag("sqlalchemy", "SQLAlchemy", ("sqlalchemy",), language="python"),
        StackTag("aiogram", "aiogram", ("aiogram",), language="python"),
        StackTag("react", "React", ("react",), language="javascript"),
        StackTag("nodejs", "Node.js", ("node.js", "nodejs", "express", "express.js"), language="javascript"),
        StackTag("vue", "Vue", ("vue", "vue.js"), language="javascript"),
        StackTag("nextjs", "Next.js", ("next.js", "nextjs"), language="javascript"),
        StackTag("nestjs", "NestJS", ("nest.js", "nestjs"), language="javascript"),
        StackTag("prisma", "Prisma", ("prisma",), language="javascript"),
        StackTag("typeorm", "TypeORM", ("typeorm",), language="javascript"),
        StackTag("sequelize", "Sequelize", ("sequelize",), language="javascript"),
        StackTag("gin", "Gin", ("gin",), language="go"),
        StackTag("echo", "Echo", ("echo",), language="go"),
        StackTag("fiber", "Fiber", ("fiber",), language="go"),
        StackTag("grpc", "gRPC", ("grpc",), language="go"),
        StackTag("gorm", "GORM", ("gorm",), language="go"),
        StackTag("spring", "Spring", ("spring", "spring boot"), language="java"),
        StackTag("hibernate", "Hibernate", ("hibernate",), language="java"),
        StackTag("mybatis", "MyBatis", ("mybatis",), language="java"),
        StackTag("junit", "JUnit", ("junit",), language="java"),
        StackTag("gradle", "Gradle", ("gradle",), language="java"),
        StackTag("aspnet", "ASP.NET", ("asp.net", "aspnet"), language="csharp"),
        StackTag("entityframework", "Entity Framework", ("entity framework", "ef core"), language="csharp"),
        StackTag("dapper", "Dapper", ("dapper",), language="csharp"),
        StackTag("blazor", "Blazor", ("blazor",), language="csharp"),
        StackTag("laravel", "Laravel", ("laravel",), language="php"),
        StackTag("symfony", "Symfony", ("symfony",), language="php"),
        StackTag("doctrine", "Doctrine", ("doctrine",), language="php"),
        StackTag("wordpress", "WordPress", ("wordpress",), language="php"),
        StackTag("rails", "Rails", ("rails", "ruby on rails"), language="ruby"),
        StackTag("sinatra", "Sinatra", ("sinatra",), language="ruby"),
        StackTag("sequel", "Sequel", ("sequel",), language="ruby"),
        StackTag("postgresql", "PostgreSQL", ("postgresql", "postgres")),
        StackTag("mysql", "MySQL", ("mysql",)),
        StackTag("mongodb", "MongoDB", ("mongodb", "mongo")),
        StackTag("redis", "Redis", ("redis",)),
        StackTag("rabbitmq", "RabbitMQ", ("rabbitmq", "amqp")),
        StackTag("kafka", "Kafka", ("kafka",)),
        StackTag("docker", "Docker/K8s", ("docker", "kubernetes", "k8s")),
    )
}

UNIVERSAL_TAG_KEYS: list[str] = [tag.key for tag in STACK_TAGS.values() if tag.language is None]


def visible_tag_keys(selected_languages: list[str]) -> list[str]:
    """Which tags to show in the "Добавить стек" flow: language-specific tags
    for each selected language (in registration order), then the universal
    infra tags."""
    language_specific = [
        tag.key for tag in STACK_TAGS.values() if tag.language is not None and tag.language in selected_languages
    ]
    return language_specific + UNIVERSAL_TAG_KEYS


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
