# jobsbot

Telegram-бот, который собирает вакансии разработчиков (Python, JavaScript/TypeScript, Go, Java, C#/.NET, PHP, Ruby) с hh.ru, LinkedIn и публичных Telegram-каналов, и присылает подписчикам только то, что реально совпадает с их языком и стеком (Django, Redis, Kafka и т.п.) — выбирается в самом боте через кнопку «➕ Добавить стек». Рассылку подписчик включает и выключает сам кнопками «👀 Смотреть вакансии» / «⏸ Остановить рассылку». Монетизация — отдельные баннерные рекламные рассылки, не вмешанные в сами вакансии.

Рассчитан на запуск на **Raspberry Pi** (через Docker), чтобы не платить за VPS.

## Подробная документация

- [`docs/stack.md`](docs/stack.md) — на чём написан сам бот (язык, библиотеки, БД).
- [`docs/sources.md`](docs/sources.md) — какие источники вакансий парсятся и как.
- [`docs/languages-and-stacks.md`](docs/languages-and-stacks.md) — полная таблица языков и тегов стека, которые пользователь выбирает через «➕ Добавить стек».
- [`docs/admin.md`](docs/admin.md) — как пользоваться админ-меню (`/admin`), права, добавление сотрудников и каналов.

## Быстрый старт (Docker)

Нужен Docker и docker-compose. Предполагается 64-битная ОС (на Raspberry Pi — Raspberry Pi OS 64-bit или Ubuntu Server arm64).

```bash
git clone <repo> && cd project_alpha
cp .env.example .env
# заполнить .env (см. таблицу переменных ниже) — как минимум BOT_TOKEN,
# DB_PASSWORD, SUPER_ADMIN_TELEGRAM_USER_ID
```

```bash
docker compose up -d
```

Этого достаточно для парсинга **hh.ru** (и опционально LinkedIn) — Telegram-каналы без `TELEGRAM_API_ID`/`TELEGRAM_API_HASH` в `.env` просто отключены (см. ниже), никакого дополнительного шага логина не нужно.

### Если нужен и парсинг Telegram-каналов

Заполни `TELEGRAM_API_ID`/`TELEGRAM_API_HASH` в `.env` (как получить — см. [my.telegram.org/apps](https://my.telegram.org/apps)). Первый запуск после этого — **обязательно в интерактивном режиме**, не `-d`: Telethon попросит номер телефона и код из Telegram, чтобы создать `.session`-файл (это отдельный user-аккаунт для чтения каналов, не сам бот):

```bash
docker compose run --rm bot python -m jobsbot.main
# ввести номер телефона, затем код из Telegram
# после того как в логах пошёл обычный поллинг — Ctrl+C
docker compose up -d   # дальше обычный запуск в фоне, .session сохранён в ./data
```

Проверить, что всё поднялось:

```bash
docker compose ps                 # оба сервиса должны быть Up / healthy
docker compose logs -f bot        # живые логи поллинга
```

### Перезапуск / обновление

Просто перечитать `.env` (без пересборки — если менял только переменные окружения):

```bash
docker compose restart bot
```

После `git pull` с новым кодом — пересобрать образ и пересоздать контейнер:

```bash
git pull
docker compose up -d --build
```

Если нужно руки полностью пересоздать контейнеры (например, что-то зависло):

```bash
docker compose down
docker compose up -d
```

`postgres` при этом не трогается — данные в volume `pgdata` сохраняются; `down -v` вместо `down` **удалит и данные БД**, так делать не нужно без явной необходимости всё стереть.

Все шаги выше (git pull → down → build --no-cache → up) одной командой — скрипт [`deploy.py`](deploy.py):

```bash
python3 deploy.py
```

### Ручные миграции схемы БД

В проекте нет Alembic — таблицы создаются один раз при самом первом старте (`SQLModel.metadata.create_all()`), **но не изменяются** на уже существующей базе при добавлении новых полей в модели. Если в очередном обновлении код добавил новые колонки (смотреть changelog/коммиты на `storage/models.py`) — перед `docker compose up -d --build` на уже работающем деплое нужно накатить `ALTER TABLE` руками, иначе бот упадёт на первом же запросе к БД с `column does not exist`.

Пример (актуален для добавления `uuid`/`experience`/`employment_type`/`schedule`/`work_format` в `vacancies`):

```bash
docker compose exec postgres psql -U "$DB_USER" -d "$DB_NAME" <<'SQL'
ALTER TABLE vacancies
  ADD COLUMN IF NOT EXISTS uuid VARCHAR,
  ADD COLUMN IF NOT EXISTS experience VARCHAR,
  ADD COLUMN IF NOT EXISTS employment_type VARCHAR,
  ADD COLUMN IF NOT EXISTS schedule VARCHAR,
  ADD COLUMN IF NOT EXISTS work_format VARCHAR;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
UPDATE vacancies SET uuid = gen_random_uuid()::text WHERE uuid IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ix_vacancies_uuid ON vacancies (uuid);
SQL
```

На **новом** деплое (чистая база, таблицы ещё не существуют) этот шаг не нужен — `create_all()` сразу создаст таблицу с полным набором колонок.

Останавливается на первом шаге, который завершился с ошибкой, и печатает код выхода — так что если что-то упало, видно сразу на каком этапе.

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
| `TELEGRAM_API_ID` | нет | — (отключено) | API ID с [my.telegram.org/apps](https://my.telegram.org/apps) — для Telethon (чтение каналов от имени user-аккаунта, не бота). Пустое — Telegram-парсинг просто выключен, hh.ru/LinkedIn работают независимо |
| `TELEGRAM_API_HASH` | нет | — (отключено) | API Hash оттуда же — должен быть задан вместе с `TELEGRAM_API_ID`, иначе Telegram-парсинг не включится |
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
- **Язык/стек, старт/стоп рассылки** — через reply-keyboard меню подписчика в самом боте (кнопки «➕ Добавить стек» / «👀 Смотреть вакансии» / «⏸ Остановить рассылку»).

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
