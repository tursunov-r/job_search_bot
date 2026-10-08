# Языки и стеки, которые доступны пользователю в боте

Справочник того, что подписчик реально видит и выбирает в флоу «➕ Добавить стек» (кнопка в reply-keyboard меню, `bot/handlers/subscriber_menu.py`) — на момент написания. Держать этот файл актуальным при добавлении нового языка/тега (или честно забить и сверяться прямо по коду — см. "Источник правды" ниже).

**Источник правды в коде**: `src/jobsbot/processing/languages.py` (языки) и `src/jobsbot/processing/stack_tags.py` (теги). Если этот файл и код расходятся — верить коду, это просто его человекочитаемый снимок.

## Как это работает (напоминание логики)

1. Пользователь нажимает «➕ Добавить стек» — сначала выбирает **сферу** (Backend/Frontend/Mobile, см. `CATEGORIES` в `languages.py`), потом язык внутри неё — сразу показывается чеклист его тегов. Уже добавленные языки отмечены ✅ и рядом есть кнопка 🗑 — убирает язык и его теги из профиля (универсальные теги типа Redis/Docker не трогает, они могут быть нужны для других языков). «⬅️ Назад» есть на каждом шаге (из списка языков — к сферам, с экрана тегов — к списку языков).
2. Один язык может быть в нескольких сферах одновременно — например, JavaScript/TS числится и в Backend (Node.js/NestJS), и в Frontend (React/Vue/Next.js). Выбор сферы — это просто фильтр, какие языки показать в списке, а не жёсткая категория самого языка.
3. На экране тегов: теги этого языка + универсальные теги (видны всегда, независимо от языка).
4. Вакансия доходит до подписчика, если: её язык совпадает хотя бы с одним выбранным языком (или язык не выбран вовсе — тогда без фильтра) **И** её текст совпадает хотя бы с одним выбранным тегом (или тег не выбран — тоже без фильтра). Сфера (Backend/Frontend/Mobile) сама по себе **не сохраняется** в профиле и не участвует в фильтрации вакансий — это только навигация в UI выбора языка.
5. Совпадение по тегу — просто проверка ключевых слов в заголовке+описании вакансии, без учёта регистра, по границам слова.

## Языки

| Язык (как видит пользователь) | Ключ в коде | Сфера(ы) | Поисковый термин на hh.ru | Ключевые слова для определения релевантности (для Telegram-каналов, где язык не известен заранее) |
|---|---|---|---|---|
| Python | `python` | Backend | `python` | `python`, `питон`, `пайтон` |
| JavaScript/TS | `javascript` | Frontend, Backend | `javascript` | `javascript`, `typescript`, `node.js`, `nodejs` |
| Go | `go` | Backend | `golang` | `golang`, `go-разработчик`, `go developer` *(голое слово "go" намеренно не используется — слишком много ложных срабатываний)* |
| Java | `java` | Backend | `java` | `java` |
| C#/.NET | `csharp` | Backend | `c#` | `c#`, `.net`, `dotnet`, `asp.net` |
| PHP | `php` | Backend | `php` | `php` |
| Ruby | `ruby` | Backend | `ruby` | `ruby`, `ruby on rails` |
| Kotlin | `kotlin` | Mobile | `kotlin` | `kotlin` |
| Swift | `swift` | Mobile | `swift` | `swift` *(слово "swift" изредка встречается в банковском контексте — SWIFT-платежи; поскольку это единственное ключевое слово, детект по описанию никогда не срабатывает — см. `_count_matches`, порог "≥2" недостижим с одним словом; риск ложного срабатывания остаётся только для заголовка)* |
| Dart/Flutter | `dart` | Mobile | `flutter` *(а не `dart` — по факту почти все вакансии ищут именно "Flutter")* | `flutter`, `dart` |
| DevOps | `devops` | DevOps | `devops` | `devops`, `девопс` |
| Системное администрирование | `sysadmin` | SysAdmin | `системный администратор` | `системный администратор`, `сисадмин`, `sysadmin` |
| QA/Тестирование | `qa` | QA | `тестировщик` | `тестировщик`, `qa engineer` |

DevOps/SysAdmin/QA — не языки программирования в обычном смысле, но заведены как записи в том же реестре `LANGUAGES` намеренно: вся остальная логика (поиск на hh.ru/Habr, детект для Telegram-каналов, группировка по сфере, теги стека) уже работает универсально поверх этой структуры, заводить отдельный параллельный механизм не было смысла.

**LinkedIn-источник — исключение**: там язык всегда жёстко `python`, независимо от реестра выше (см. `docs/sources.md`).

## Теги стека

### Привязанные к языку (показываются сразу после выбора языка в «➕ Добавить стек»)

| Тег (как видит пользователь) | Ключ | Язык | Ключевые слова |
|---|---|---|---|
| Django | `django` | Python | `django` |
| Flask | `flask` | Python | `flask` |
| FastAPI | `fastapi` | Python | `fastapi` |
| Celery | `celery` | Python | `celery` |
| Pandas/NumPy | `pandas` | Python | `pandas`, `numpy` |
| SQLAlchemy | `sqlalchemy` | Python | `sqlalchemy` |
| aiogram | `aiogram` | Python | `aiogram` |
| React | `react` | JavaScript/TS | `react` |
| Node.js | `nodejs` | JavaScript/TS | `node.js`, `nodejs`, `express`, `express.js` |
| Vue | `vue` | JavaScript/TS | `vue`, `vue.js` |
| Next.js | `nextjs` | JavaScript/TS | `next.js`, `nextjs` |
| NestJS | `nestjs` | JavaScript/TS | `nest.js`, `nestjs` |
| Prisma | `prisma` | JavaScript/TS | `prisma` |
| TypeORM | `typeorm` | JavaScript/TS | `typeorm` |
| Sequelize | `sequelize` | JavaScript/TS | `sequelize` |
| Gin | `gin` | Go | `gin` |
| Echo | `echo` | Go | `echo` |
| Fiber | `fiber` | Go | `fiber` |
| gRPC | `grpc` | Go | `grpc` |
| GORM | `gorm` | Go | `gorm` |
| Spring | `spring` | Java | `spring`, `spring boot` |
| Hibernate | `hibernate` | Java | `hibernate` |
| MyBatis | `mybatis` | Java | `mybatis` |
| JUnit | `junit` | Java | `junit` |
| Gradle | `gradle` | Java | `gradle` |
| ASP.NET | `aspnet` | C#/.NET | `asp.net`, `aspnet` |
| Entity Framework | `entityframework` | C#/.NET | `entity framework`, `ef core` |
| Dapper | `dapper` | C#/.NET | `dapper` |
| Blazor | `blazor` | C#/.NET | `blazor` |
| Laravel | `laravel` | PHP | `laravel` |
| Symfony | `symfony` | PHP | `symfony` |
| Doctrine | `doctrine` | PHP | `doctrine` |
| WordPress | `wordpress` | PHP | `wordpress` |
| Rails | `rails` | Ruby | `rails`, `ruby on rails` |
| Sinatra | `sinatra` | Ruby | `sinatra` |
| Sequel | `sequel` | Ruby | `sequel` |
| Jetpack Compose | `jetpackcompose` | Kotlin | `jetpack compose`, `jetpack` |
| Room | `room` | Kotlin | `room` |
| Retrofit | `retrofit` | Kotlin | `retrofit` |
| Coroutines | `coroutines` | Kotlin | `coroutines` |
| Ktor | `ktor` | Kotlin | `ktor` |
| SwiftUI | `swiftui` | Swift | `swiftui` |
| UIKit | `uikit` | Swift | `uikit` |
| Combine | `combine` | Swift | `combine` |
| Core Data | `coredata` | Swift | `core data`, `coredata` |
| Alamofire | `alamofire` | Swift | `alamofire` |
| GetX | `getx` | Dart/Flutter | `getx` |
| BLoC | `bloc` | Dart/Flutter | `bloc` |
| Provider | `provider` | Dart/Flutter | `provider` |
| Dio | `dio` | Dart/Flutter | `dio` |
| Terraform | `terraform` | DevOps | `terraform` |
| Ansible | `ansible` | DevOps | `ansible` |
| Jenkins | `jenkins` | DevOps | `jenkins` |
| Prometheus/Grafana | `prometheus` | DevOps | `prometheus`, `grafana` |
| GitLab CI | `gitlabci` | DevOps | `gitlab ci`, `gitlab-ci` |
| Linux | `linuxadmin` | SysAdmin | `linux` |
| Windows Server | `windowsserver` | SysAdmin | `windows server` |
| Active Directory | `activedirectory` | SysAdmin | `active directory` |
| Zabbix | `zabbix` | SysAdmin | `zabbix` |
| Bash/Shell | `bashscripting` | SysAdmin | `bash`, `shell script` |
| Selenium | `selenium` | QA | `selenium` |
| Postman | `postman` | QA | `postman` |
| Cypress | `cypress` | QA | `cypress` |
| Playwright | `playwright` | QA | `playwright` |
| JMeter | `jmeter` | QA | `jmeter` |

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

Языки, которые НЕ покрыты ни HH-поллингом, ни детектом для Telegram-каналов: C/C++, Rust, Scala, Elixir, 1C. Добавляются по тому же паттерну — см. любой из коммитов `feat: add <язык> language + stack tags` в истории git для образца (новая запись в `LANGUAGES`, несколько тегов в `STACK_TAGS` с `language=<ключ>`, тест на детект в `tests/test_languages.py`).
