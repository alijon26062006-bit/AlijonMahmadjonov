# AVERIX Freelance — аудит и план

Документ написан до первой строки кода маркетплейса. Пять частей,
которых требует задание: карта репозитория, карта архитектуры, карта
базы, карта рисков безопасности, план внедрения.

Ветка работы: `feature/averix-freelance-marketplace`
(отходит от `claude/ui-ux-pro-max-landing-n9y2jh`, push — в неё же).

---

## 1. Карта репозитория

Стек проверен по коду, не по предположениям.

| Слой | Что стоит | Где |
|---|---|---|
| Backend | FastAPI, синхронные функции, без ORM | `app/*.py` |
| Шаблоны | Jinja2, серверный рендер, без сборки фронтенда | `app/templates/` |
| База | SQLite, WAL, `sqlite3` из стандартной библиотеки | `app/db.py` |
| Миграции | нумерованные `.sql`, учёт в `schema_migrations` | `app/migrations/` |
| Фронтенд | один `styles.css` (903 строки), один `app.js` (644), без бандлера | корень |
| Загрузки | Pillow, пересохранение в WebP, случайные имена | `app/uploads.py` |
| Прокси | nginx: статика с диска по белому списку, остальное в приложение | `deploy/nginx.conf` |
| Процесс | systemd, uvicorn, 2 воркера, миграции в `ExecStartPre` | `deploy/averix.service` |
| Тесты | pytest + `TestClient`, 70 штук, временная папка данных | `tests/` |
| Журнал | stdout → journald, секреты вырезаются по именам полей | `app/journal.py` |

Ключевое для маркетплейса: **сборки фронтенда нет**. «Production build»
здесь — это не webpack, а: миграции применяются, приложение стартует
под gunicorn/uvicorn с рабочими настройками, nginx отдаёт страницы,
тесты зелёные. Ставить React ради маркетплейса — это и есть та самая
замена архитектуры, которую задание запрещает.

### Модули backend

| Файл | Строк | Отвечает за |
|---|---|---|
| `main.py` | 471 | вход админа, проекты, картинки, обработчики ошибок |
| `models.py` | 539 | проекты, настройки, команда, вакансии, заявки |
| `work.py` | 471 | специалисты студии, клиентские проекты, задачи |
| `routes_public.py` | 354 | публичные страницы и формы |
| `routes_admin_studio.py` | 399 | настройки, команда, вакансии, отклики |
| `routes_admin_work.py` | 407 | специалисты, клиентские проекты, задачи, журнал |
| `routes_freelancer.py` | 268 | кабинет специалиста студии |
| `security.py` | 144 | scrypt, сессии, CSRF, защита от перебора |
| `adminkit.py` | 79 | guard админки, страницы ошибок |
| `render.py` | 65 | шаблоны, язык, контекст, `client_ip`, `is_secure` |
| `audit.py` | 52 | журнал действий админа, закрытый список действий |
| `notify.py` | 84 | уведомления в базу + Telegram в фоне |
| `uploads.py` | 101 | приём картинок |

---

## 2. Карта архитектуры

### Роли сейчас

| Роль | Таблица учёток | Таблица сессий | Cookie | Вход |
|---|---|---|---|---|
| Администратор | `admins` | `sessions` | `averix_session` | `/admin` |
| Специалист студии | `freelancers` | `freelancer_sessions` | `averix_worker` | `/freelancer/login` |
| Посетитель | — | — | — | — |

Разделение сессий по ролям сделано намеренно и остаётся: общая таблица
однажды выдала бы одной роли токен другой.

### Как устроена авторизация

`guard()` в `adminkit.py` и свой `guard()` в `routes_freelancer.py`.
Оба серверные, оба стоят первой строкой каждого защищённого маршрута.
Владелец задачи стоит **внутри SQL-запроса** (`freelancer_task`), а не
в проверке после выборки — чужая строка не попадает в данные вовсе.
Этот приём переносится в маркетплейс без изменений.

### Что переиспользуется, что расширяется, что новое

**СУЩЕСТВУЕТ И ГОДИТСЯ КАК ЕСТЬ**

- `security.py` целиком: scrypt, `_token_hash`, CSRF, `recent_failures`,
  `login_delay`, `is_blocked`. Регистрация и сброс пароля садятся сюда же.
- `uploads.py`: проверка сигнатуры, снятие EXIF, пережатие в WebP,
  случайное имя. Для аватаров и портфолио менять нечего.
- `notify.py`: уведомления в базу + Telegram в фоне.
- `journal.py`: вырезание секретов по именам полей.
- `db.py` + механизм миграций.
- `adminkit.page()`, `error_page`, `no_store`, `render.client_ip/is_secure`.
- nginx: белый список статики, CSP, заголовки. Правок не требует, кроме
  одной (см. риски: загрузки маркетплейса).

**СУЩЕСТВУЕТ, НО ТРЕБУЕТ РАСШИРЕНИЯ**

- `freelancers` — становится профилем специалиста маркетплейса:
  добавляются `user_id`, `title`, `category_id`, `experience_level`,
  `listing`, `public_slug`, `published_at`. Существующие строки
  остаются частной базой студии (`user_id IS NULL`, `listing='hidden'`).
- `audit.ACTIONS` — закрытый словарь, нужны новые действия маркетплейса.
- `notifications` — сейчас это уведомления **админу**. Пользовательские
  уведомления живут отдельно (`fl_notifications`), смешивать нельзя:
  у админских нет адресата.
- `sitemap.xml` — добавить публичные разделы маркетплейса.
- Админка: новый раздел FREELANCE внутри существующей панели.
- `styles.css` — приложение получает **свой** файл `app-freelance.css`.
  Сайт-витрину не трогаем: она только что доведена и проверена.

**ОТСУТСТВУЕТ ПОЛНОСТЬЮ**

Учётные записи по email, роли заказчик/специалист, таксономия категорий
и навыков, проекты заказчиков, отклики, контракты, этапы, рабочее
пространство, переписка, уведомления пользователю, отзывы и рейтинг,
избранное, услуги, жалобы, споры, продвижение, реклама, восстановление
пароля, пагинация.

**ОПАСНО ТРОГАТЬ**

| Что | Почему |
|---|---|
| `tasks.freelancer_id → freelancers.id` | внутренняя работа студии; перенос `freelancers` в новую таблицу порвёт задачи |
| `freelancer_sessions` и `/freelancer/*` | у специалистов студии могут быть живые входы |
| CHECK-ограничения в SQLite | меняются только пересборкой таблицы |
| CSP с sha256 встроенного скрипта | любой новый встроенный `<script>` молча не выполнится |
| `update.sh` делает `git reset --hard` | править файлы на сервере нельзя |
| Обещание под формами | «Данные из формы видит только студия. Мы не публикуем их…» — старые анкеты публиковать нельзя ни при каких условиях |

---

## 3. Карта базы

### Что есть (19 таблиц)

```
admins, sessions, login_attempts
projects, project_images, project_tech, site_settings
team_members, vacancies, job_applications, client_requests
freelancers, freelancer_sessions
client_projects, tasks, task_history
notifications, admin_log, schema_migrations
```

Две вещи, которые нельзя перепутать и дальше:

- `projects` — публичное портфолио студии. `client_projects` — внутренняя
  работа с заказчиком. Новое `fl_projects` — **третье**: заказы на бирже.
  Три разные сущности с похожими именами; префикс `fl_` обязателен.
- `notifications` — админу. `fl_notifications` — пользователю.

### Что добавляется

Ни одной колонки `*_ru`/`*_tj` в таблицах маркетплейса: приложение
русскоязычное, как требует задание. Двуязычность остаётся у витрины.

Деньги — только целые в минорных единицах (`INTEGER`), никакого
плавающего. Валюта настраивается в админке (`freelance_currency`).

```
006_users.sql
  users(id, email UNIQUE NOCASE, password_hash, telegram, status,
        email_verified, created_at, updated_at, last_seen_at)
  user_sessions(token_hash PK, user_id, csrf_token, created_at,
        expires_at, ip, user_agent)
  password_resets(token_hash PK, user_id, expires_at, used_at, created_at)
  client_profiles(id, user_id UNIQUE, display_name, about, location,
        avatar, created_at, updated_at)
  ALTER freelancers: user_id, title, category_id, experience_level,
        listing, public_slug, published_at, source
  UNIQUE INDEX freelancers(user_id) WHERE user_id IS NOT NULL

007_taxonomy.sql
  fl_categories(id, parent_id, name, slug UNIQUE, sort_order, enabled)
  fl_skills(id, name, slug UNIQUE, category_id, enabled, merged_into_id)
  fl_freelancer_skills(freelancer_id, skill_id) PK обе

008_projects.sql
  fl_projects(id, client_user_id, title, slug UNIQUE, description,
        category_id, subcategory_id, budget_type, budget_min, budget_max,
        currency, deadline, experience_level, visibility, status,
        proposals_count, published_at, created_at, updated_at)
  fl_project_skills(project_id, skill_id)
  fl_project_files(id, project_id, filename, original_name, bytes, mime)
  fl_proposals(id, project_id, freelancer_user_id, price, days,
        cover_letter, status, created_at, updated_at)
        UNIQUE(project_id, freelancer_user_id)

009_contracts.sql
  fl_contracts(id, project_id, proposal_id, client_user_id,
        freelancer_user_id, title, amount, status, created_at, closed_at)
  fl_milestones(id, contract_id, title, description, amount, deadline,
        status, sort_order)
  fl_submissions(id, milestone_id, author_user_id, message, url, created_at)
  fl_submission_files(id, submission_id, filename, original_name, bytes)
  fl_contract_events(id, contract_id, actor_user_id, from_status,
        to_status, comment, created_at)

010_messages.sql
  fl_conversations(id, kind, contract_id, created_at, last_message_at)
  fl_conversation_members(conversation_id, user_id, last_read_at) PK обе
  fl_messages(id, conversation_id, author_user_id, body, created_at)
  fl_message_files(id, message_id, filename, original_name, bytes)

011_reviews.sql
  fl_reviews(id, contract_id, author_user_id, target_user_id, role,
        rating, score_quality, score_deadlines, score_communication,
        comment, revealed_at, created_at)
        UNIQUE(contract_id, author_user_id)

012_market.sql
  fl_favorites(user_id, kind, target_id) PK все три
  fl_notifications(id, user_id, kind, title, url, read_at, created_at)
  fl_reports(id, reporter_user_id, kind, target_id, reason, comment,
        status, created_at)
  fl_disputes(id, contract_id, opened_by_user_id, reason, description,
        status, resolution, created_at, updated_at)
  fl_blocks(user_id, blocked_user_id) PK обе

013_services.sql
  fl_services(id, freelancer_user_id, title, slug UNIQUE, category_id,
        description, includes, price, days, revisions, status,
        created_at, updated_at)
  fl_service_images(id, service_id, filename, sort_order)
  fl_service_packages(id, service_id, level, title, price, days, includes)

014_promo.sql
  fl_promotions(id, kind, target_id, starts_at, ends_at, created_by)
  fl_ads(id, title, image, url, placement, starts_at, ends_at, enabled)
  fl_moderation_log(id, admin_id, entity, entity_id, action, reason,
        created_at)
```

### Ограничения на уровне базы (не только кода)

- `UNIQUE(project_id, freelancer_user_id)` в `fl_proposals` — второй
  отклик на тот же проект физически не запишется.
- `UNIQUE(contract_id, author_user_id)` в `fl_reviews` — второй отзыв
  по одному контракту от одной стороны невозможен.
- `UNIQUE INDEX users(email)` с `COLLATE NOCASE` — регистр не создаёт
  вторую учётку.
- `fl_conversation_members` — участие в переписке проверяется
  соединением, а не сравнением после выборки.

---

## 4. Карта рисков безопасности

Отсортировано по цене ошибки.

| # | Риск | Где | Что делаем |
|---|---|---|---|
| 1 | **IDOR** — маркетплейс весь состоит из чужих номеров | проекты, отклики, контракты, этапы, переписка, файлы | владелец/участник стоит **в самом SQL-запросе**, как уже сделано в `freelancer_task`. Отдельный тестовый файл на каждый ресурс: чужой id → 404 |
| 2 | **Повышение прав** | формы профиля и проекта | список колонок задан в коде (`FREELANCER_COLUMNS`), из формы берутся только разрешённые поля. Ни `status`, ни `rating`, ни `listing` через форму не проходят |
| 3 | **Утечка личных данных** | email, Telegram, приложенные файлы, переписка | контакты в каталоге не показываются вообще; связь через форму. Файлы отдаются приложением с проверкой прав, а не nginx напрямую |
| 4 | **Старые анкеты** | `freelancers` | всем существующим строкам `listing='hidden'`, `user_id NULL`. Опубликовать может только сам человек из своего кабинета |
| 5 | **Загрузка файлов** | аватары, портфолио, вложения | картинки — через `uploads.py`. Документы (ТЗ, вложения) — новый модуль: белый список MIME, проверка сигнатуры, случайное имя, отдача через приложение с `Content-Disposition: attachment` |
| 6 | **Перебор** | вход, регистрация, сброс пароля | общий счётчик `login_attempts` по IP; регистрация и сброс — отдельные лимиты |
| 7 | **Перечисление адресов** | регистрация, сброс пароля | один ответ на всё: «Если такой адрес есть, письмо отправлено». Регистрация с занятым адресом — сообщение об ошибке нужно, но без подсказки; решение: подтверждение по почте |
| 8 | **CSRF** | все формы | токен в сессии, `check_csrf` на каждом POST |
| 9 | **XSS** | описания, отклики, сообщения | Jinja2 экранирует по умолчанию; `|safe` в маркетплейсе не применять нигде. Отдельный тест на сохранённый XSS |
| 10 | **Открытый редирект** | `?next=` после входа | принимать только относительные пути, начинающиеся с `/freelance` |
| 11 | **Фиксация сессии** | вход | новый токен на каждый вход; смена пароля закрывает все сессии |
| 12 | **Гонка при отклике** | двойной клик | `UNIQUE(project_id, freelancer_user_id)` + перехват `IntegrityError` |
| 13 | **N+1 и тяжёлые выборки** | лента проектов, каталог | пагинация по курсору, индексы на `(status, published_at)`, счётчик откликов колонкой |
| 14 | **Деньги** | суммы, комиссия | `INTEGER` в минорных единицах, расчёты только на сервере, комиссия в настройках |
| 15 | **Ложные обещания** | интерфейс | ни «эскроу», ни «личность подтверждена», ни «отвечает за 5 минут» без реальной реализации |

### Отдельно: чего не будет

Настоящего платёжного провайдера в проекте нет. Значит:

- слой оплаты делается как **интерфейс** (`payments.py` с абстрактным
  провайдером и заглушкой `NoProvider`), состояния наружу не
  показываются, пока провайдера нет;
- слова «средства защищены», «эскроу», «безопасная сделка» в интерфейсе
  не появляются;
- в документации будет прямо написано: реально реализовано —
  договорённость о цене внутри контракта и её фиксация; не реализовано —
  движение денег.

---

## 5. План внедрения

Каждая фаза — миграция, код, шаблоны, тесты, регрессия витрины.
Красный тест — переход к следующей фазе запрещён.

| # | Фаза | Готово, когда |
|---|---|---|
| 1 | Учётные записи и вход | регистрация, вход, выход, срок сессии, сброс пароля, лимиты; тесты на перебор и перечисление адресов |
| 2 | Таксономия | категории и навыки из базы, управление в админке, слияние дубликатов |
| 3 | Профиль специалиста | онбординг по шагам, портфолио, каталог `/freelance/specialists`, публичная карточка, модерация публикации |
| 4 | Заказчик и проекты | профиль заказчика, создание проекта шагами с черновиком, лента `/freelance/projects`, фильтры, поиск, страница проекта |
| 5 | Отклики и контракты | отклик, список откликов у заказчика, выбор исполнителя, контракт, этапы, рабочее пространство, сдача и приёмка работы |
| 6 | Переписка и уведомления | `/freelance/messages`, вложения, счётчик непрочитанных, колокольчик |
| 7 | Отзывы и рейтинг | отзыв только по завершённому контракту, двусторонняя слепая схема, рейтинг считается запросом |
| 8 | Избранное и услуги | сохранённые проекты и специалисты, каталог услуг, создание услуги, модерация |
| 9 | Админка Freelance | раздел в панели, модерация с причиной, жалобы, споры, продвижение с пометкой «Продвижение», реклама с пометкой «Реклама», настройки комиссии |
| 10 | Финал | SEO и sitemap, пагинация везде, мобильные и планшетные проверки, регрессия витрины, итоговый аудит PASS/FAIL, документация на русском |

### Что проверяется после каждой фазы

1. `pytest` целиком (сейчас 70 тестов — ни один не должен покраснеть).
2. `python -m compileall app` — синтаксис.
3. Запуск приложения с рабочими настройками, миграции применяются.
4. Живые страницы через nginx: консоль браузера пустая, горизонтальной
   прокрутки нет, ширины 360 / 390 / 430 / 768 / 1024 / 1440.
5. Проверка прав чужой сессией: каждый новый номер в адресе.
6. Витрина: главная, проекты, кейс, студия, вакансии, админка.

### Порядок URL

```
/                         витрина студии            (не трогаем)
/projects, /team, /careers                          (не трогаем)
/admin/*                  админка                   (расширяем)
/freelancer/*             кабинет специалиста студии (не трогаем)

/freelance                        вход в маркетплейс
/freelance/register  /login  /logout  /reset
/freelance/projects               лента заказов
/freelance/projects/create
/freelance/projects/{slug}
/freelance/specialists            каталог специалистов
/freelance/specialists/{slug}
/freelance/services
/freelance/dashboard              кабинет пользователя
/freelance/messages
/freelance/workspace/{id}
/freelance/saved/*
/admin/freelance/*                модерация
```

Старая анкета «стать специалистом в базе студии» никуда не исчезает:
страница переезжает на `/freelance/studio`, адрес формы
`POST /freelance/apply` сохраняется — на него могут ссылаться закладки.
