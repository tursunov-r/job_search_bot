# jobsbot

Telegram-бот, который собирает вакансии разработчиков (Python, JavaScript/TypeScript, Go, Java, C#/.NET, PHP, Ruby) с hh.ru, LinkedIn и публичных Telegram-каналов, и присылает подписчикам только то, что реально совпадает с их языком и стеком (Django, Redis, Kafka и т.п.) — выбирается в самом боте через `/language` и `/stack`. Монетизация — отдельные баннерные рекламные рассылки, не вмешанные в сами вакансии.

Рассчитан на запуск на **Raspberry Pi** (через Docker), чтобы не платить за VPS.

## Подробная документация

- [`docs/stack.md`](docs/stack.md) — на чём написан сам бот (язык, библиотеки, БД).
- [`docs/sources.md`](docs/sources.md) — какие источники вакансий парсятся и как.
- [`docs/admin.md`](docs/admin.md) — как пользоваться админ-меню (`/admin`), права, добавление сотрудников и каналов.

## Быстрый старт (Docker)

Нужен Docker и docker-compose. Предполагается 64-битная ОС (на Raspberry Pi — Raspberry Pi OS 64-bit или Ubuntu Server arm64).

```bash
git clone <repo> && cd project_alpha
cp .env.example .env
# заполнить .env (см. таблицу переменных ниже) — как минимум BOT_TOKEN,
# TELEGRAM_API_ID/HASH, DB_PASSWORD, SUPER_ADMIN_TELEGRAM_USER_ID
```

Первый запуск — **обязательно в интерактивном режиме**, не `-d`: Telethon при первом старте попросит номер телефона и код из Telegram, чтобы создать `.session`-файл (это отдельный user-аккаунт для чтения каналов, не сам бот).

```bash
docker compose run --rm bot python -m jobsbot.main
# ввести номер телефона, затем код из Telegram
# после того как в логах пошёл обычный поллинг — Ctrl+C
```

Дальше обычный запуск в фоне — `.session`-файл сохранён в `./data` (volume), повторного логина не требуется:

```bash
docker compose up -d
```

Проверить, что всё поднялось:

```bash
docker compose ps                 # оба сервиса должны быть Up / healthy
docker compose logs -f bot        # живые логи поллинга
```

## Локальный запуск без Docker (для разработки)

Нужен Python 3.11+ и запущенный где-то Postgres (например, `docker run -d -e POSTGRES_PASSWORD=... -p 5432:5432 postgres:16-alpine`).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env   # заполнить, DB_HOST=localhost если Postgres локально
python -m jobsbot.main
```

Тесты (не требуют БД — чистая логика):

```bash
pip install -e ".[dev]"
PYTHONPATH=src pytest tests/ -v
```

## Переменные окружения (`.env`)

| Переменная | Обязательна | По умолчанию | Что это |
|---|---|---|---|
| `BOT_TOKEN` | да | — | Токен Telegram-бота от [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_API_ID` | да | — | API ID с [my.telegram.org](https://my.telegram.org) — для Telethon (чтение каналов от имени user-аккаунта, не бота) |
| `TELEGRAM_API_HASH` | да | — | API Hash оттуда же |
| `TELEGRAM_SESSION_PATH` | нет | `data/telegram_user.session` | Путь к файлу Telethon-сессии. В Docker это должно быть внутри примонтированного `./data`, иначе сессия потеряется при пересборке контейнера |
| `TELEGRAM_POLL_INTERVAL_SECONDS` | нет | `300` | Как часто (сек) опрашивать Telegram-каналы на новые сообщения |
| `HH_SEARCH_URL` | нет | `https://hh.ru/search/vacancy` | База URL для парсинга поиска hh.ru (менять не нужно, если hh.ru не переедет) |
| `HH_POLL_INTERVAL_SECONDS` | нет | `600` | Как часто (сек) опрашивать hh.ru (один цикл = запрос на каждый поддерживаемый язык) |
| `LINKEDIN_ENABLED` | нет | `false` | Включить парсинг LinkedIn — самый юридически рискованный источник, см. [`docs/sources.md`](docs/sources.md) |
| `LINKEDIN_POLL_INTERVAL_SECONDS` | нет | `3600` | Как часто (сек) опрашивать LinkedIn, если включён |
| `VACANCY_PUSH_INTERVAL_SECONDS` | нет | `180` | Как часто (сек) рассылать подписчикам накопившиеся новые вакансии |
| `AD_BROADCAST_CHECK_INTERVAL_SECONDS` | нет | `1800` | Как часто (сек) проверять, не пора ли разослать очередную рекламную кампанию |
| `DB_HOST` | нет | `postgres` | Хост Postgres. `postgres` — имя сервиса в docker-compose; для локального запуска без Docker — `localhost` |
| `DB_PORT` | нет | `5432` | Порт Postgres |
| `DB_NAME` | нет | `jobsbot` | Имя базы данных |
| `DB_USER` | нет | `jobsbot` | Пользователь Postgres |
| `DB_PASSWORD` | да | — | Пароль Postgres. Используется и приложением, и сервисом `postgres` в docker-compose (`POSTGRES_PASSWORD`) — значение из одной переменной, без дублирования |
| `SUPER_ADMIN_TELEGRAM_USER_ID` | да | — | Числовой Telegram ID супер-админа (не username). Получает все права автоматически, добавляет сотрудников через `/admin` — см. [`docs/admin.md`](docs/admin.md) |

Полный шаблон со всеми переменными — в [`.env.example`](.env.example).

## Что не настраивается через `.env`

Сознательно вынесено в саму БД/бота, не в конфиг — потому что должно меняться без передеплоя:

- **Список Telegram-каналов для парсинга** — через `/admin` → "📡 Каналы" (не переменная окружения).
- **Сотрудники и их права** — через `/admin` → "👥 Сотрудники".
- **Язык/стек каждого подписчика** — через `/language` и `/stack` в самом боте.

## Структура проекта

```
src/jobsbot/
  main.py              — точка входа, сборка планировщика и бота
  config.py            — настройки из .env (pydantic-settings)
  bot/                 — aiogram: диспетчер, хендлеры команд, права, пуш вакансий
  ingestion/           — адаптеры источников (hh.ru, LinkedIn, Telegram-поллер)
  processing/          — дедуп, фильтр релевантности по языкам, теги стека
  ads/                 — рекламные кампании
  storage/             — модели SQLModel, доступ к БД
tests/                 — юнит-тесты (чистая логика, без БД/сети)
docs/                  — стек, источники, админка (см. выше)
Dockerfile, docker-compose.yml
```
