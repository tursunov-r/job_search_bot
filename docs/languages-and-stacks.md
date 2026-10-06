# Языки и стеки, которые доступны пользователю в боте

Справочник того, что подписчик реально видит и выбирает в `/language` и `/stack` — на момент написания. Держать этот файл актуальным при добавлении нового языка/тега (или честно забить и сверяться прямо по коду — см. "Источник правды" ниже).

**Источник правды в коде**: `src/jobsbot/processing/languages.py` (языки) и `src/jobsbot/processing/stack_tags.py` (теги). Если этот файл и код расходятся — верить коду, это просто его человекочитаемый снимок.

## Как это работает (напоминание логики)

1. Пользователь выбирает один или несколько языков в `/language`.
2. В `/stack` показываются: теги выбранных языков + универсальные теги (видны всегда, независимо от языка).
3. Вакансия доходит до подписчика, если: её язык совпадает хотя бы с одним выбранным языком (или язык не выбран вовсе — тогда без фильтра) **И** её текст совпадает хотя бы с одним выбранным тегом (или тег не выбран — тоже без фильтра).
4. Совпадение по тегу — просто проверка ключевых слов в заголовке+описании вакансии, без учёта регистра, по границам слова.

## Языки (`/language`)

| Язык (как видит пользователь) | Ключ в коде | Поисковый термин на hh.ru | Ключевые слова для определения релевантности (для Telegram-каналов, где язык не известен заранее) |
|---|---|---|---|
| Python | `python` | `python` | `python`, `питон`, `пайтон` |
| JavaScript/TS | `javascript` | `javascript` | `javascript`, `typescript`, `node.js`, `nodejs` |
| Go | `go` | `golang` | `golang`, `go-разработчик`, `go developer` *(голое слово "go" намеренно не используется — слишком много ложных срабатываний)* |
| Java | `java` | `java` | `java` |
| C#/.NET | `csharp` | `c#` | `c#`, `.net`, `dotnet`, `asp.net` |
| PHP | `php` | `php` | `php` |
| Ruby | `ruby` | `ruby` | `ruby`, `ruby on rails` |

**LinkedIn-источник — исключение**: там язык всегда жёстко `python`, независимо от реестра выше (см. `docs/sources.md`).

## Теги стека (`/stack`)

### Привязанные к языку (видны только если язык выбран в `/language`)

| Тег (как видит пользователь) | Ключ | Язык | Ключевые слова |
|---|---|---|---|
| Django | `django` | Python | `django` |
| Flask | `flask` | Python | `flask` |
| FastAPI | `fastapi` | Python | `fastapi` |
| Celery | `celery` | Python | `celery` |
| Pandas/NumPy | `pandas` | Python | `pandas`, `numpy` |
| React | `react` | JavaScript/TS | `react` |
| Node.js | `nodejs` | JavaScript/TS | `node.js`, `nodejs`, `express`, `express.js` |
| Vue | `vue` | JavaScript/TS | `vue`, `vue.js` |
| Next.js | `nextjs` | JavaScript/TS | `next.js`, `nextjs` |
| NestJS | `nestjs` | JavaScript/TS | `nest.js`, `nestjs` |
| Gin | `gin` | Go | `gin` |
| Echo | `echo` | Go | `echo` |
| Fiber | `fiber` | Go | `fiber` |
| gRPC | `grpc` | Go | `grpc` |
| Spring | `spring` | Java | `spring`, `spring boot` |
| Hibernate | `hibernate` | Java | `hibernate` |
| JUnit | `junit` | Java | `junit` |
| Gradle | `gradle` | Java | `gradle` |
| ASP.NET | `aspnet` | C#/.NET | `asp.net`, `aspnet` |
| Entity Framework | `entityframework` | C#/.NET | `entity framework`, `ef core` |
| Blazor | `blazor` | C#/.NET | `blazor` |
| Laravel | `laravel` | PHP | `laravel` |
| Symfony | `symfony` | PHP | `symfony` |
| WordPress | `wordpress` | PHP | `wordpress` |
| Rails | `rails` | Ruby | `rails`, `ruby on rails` |
| Sinatra | `sinatra` | Ruby | `sinatra` |

### Универсальные (видны всегда, при любом выбранном языке или без него)

| Тег | Ключ | Ключевые слова |
|---|---|---|
| PostgreSQL | `postgresql` | `postgresql`, `postgres` |
| MySQL | `mysql` | `mysql` |
| MongoDB | `mongodb` | `mongodb`, `mongo` |
| Redis | `redis` | `redis` |
| RabbitMQ | `rabbitmq` | `rabbitmq`, `amqp` |
| Kafka | `kafka` | `kafka` |
| Docker/K8s | `docker` | `docker`, `kubernetes`, `k8s` |

## Чего пока нет (идеи на будущее, список для себя)

Языки, которые НЕ покрыты ни HH-поллингом, ни детектом для Telegram-каналов: Kotlin, Swift, C/C++, Rust, Scala, Elixir, Dart/Flutter, 1C. Добавляются по тому же паттерну — см. любой из коммитов `feat: add <язык> language + stack tags` в истории git для образца (новая запись в `LANGUAGES`, несколько тегов в `STACK_TAGS` с `language=<ключ>`, тест на детект в `tests/test_languages.py`).
