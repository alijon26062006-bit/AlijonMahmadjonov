# 🎬 CineWave — Telegram Mini App для анонсов фильмов, сериалов, аниме и мультфильмов

Премиальная платформа уровня Netflix / Apple TV, полностью на **PHP 8.3 + MySQL 8**, без фреймворков.
Весь контент добавляется **через Telegram-бота администратора** и мгновенно появляется в Mini App.

- **Backend:** чистый PHP (MVC), PDO, подготовленные запросы, REST API
- **Frontend:** HTML5 / CSS3 / Vanilla ES6 + Telegram WebApp SDK
- **Bot:** Telegram Bot API (webhook), пошаговое добавление контента, рассылки, статистика
- Работает на **обычном shared-хостинге** — без Composer, Node.js, Laravel, React и т.п.

---

## 📁 Структура

```
project/
├── bot/          # Telegram-бот (webhook, админ-панель, FSM добавления контента)
├── miniapp/      # Frontend Mini App (index.php — SPA-оболочка)
├── api/          # REST API (MVC: core / models / controllers)
├── config/       # Конфигурация (config.php)
├── database/     # schema.sql + seed.sql (демо-данные)
├── uploads/      # Загруженные постеры/фоны/скриншоты (posters, banners, trailers, screenshots)
├── assets/       # css / js / images / icons / fonts
├── logs/         # Логи ошибок
└── vendor/       # (не используется — Composer не требуется)
```

## 🗄️ База данных

Таблицы: `users`, `admins`, `movies`, `announcements`, `genres`, `movie_genres`,
`favorites`, `history`, `views`, `banners`, `settings`, `notifications`, `bot_states`.

```bash
mysql -u root -p < database/schema.sql      # структура + жанры + настройки
mysql -u root -p cinema < database/seed.sql # (опционально) демо-контент
```

## ⚙️ Настройка

Отредактируйте `config/config.php` **или** задайте переменные окружения (они имеют приоритет):

| Переменная | Назначение |
|---|---|
| `DB_HOST` `DB_PORT` `DB_NAME` `DB_USER` `DB_PASS` | Доступ к MySQL |
| `BOT_TOKEN` | Токен бота от @BotFather |
| `MINIAPP_URL` | https-адрес папки `miniapp/` |
| `WEBHOOK_URL` | https-адрес `bot/webhook.php` |
| `WEBHOOK_SECRET` | Случайная строка (проверка подлинности вебхука) |
| `ADMIN_IDS` | Telegram ID админов через запятую, напр. `123,456` |
| `UPLOADS_URL` | https-адрес папки `uploads/` |
| `OPENAI_API_KEY` | Ключ OpenAI (только на сервере, в JS не передаётся) |
| `OPENAI_MODEL_VISION` `OPENAI_MODEL_TEXT` | Модели (по умолчанию `gpt-4o-mini`) |
| `APP_NAME` `BASE_URL` `APP_DEBUG` | Прочее |

## 🤖 Запуск бота

1. Создайте бота у **@BotFather**, получите токен, укажите его в конфиге.
2. В **@BotFather → Bot Settings → Menu Button / Web App** укажите `MINIAPP_URL`.
3. Зарегистрируйте вебхук — один раз:
   ```bash
   php bot/set_webhook.php
   # или откройте в браузере: https://ваш-домен/project/bot/set_webhook.php?key=<WEBHOOK_SECRET>
   ```
4. Напишите боту `/start`. Админам доступна панель: `/admin`.

### Что умеет админ (в Telegram)
➕ Фильм · ➕ Сериал · ➕ Мультфильм · ➕ Аниме · 📣 Анонс · 🗑 Удалить ·
📊 Статистика · 📢 Рассылка · ⚙ Настройки.
Добавление — пошаговый диалог (название → описание → постер → фон → трейлер → жанры →
страна → дата → возраст → длительность → рейтинг → язык → режиссёр → актёры →
ссылка → статус). Медиа сохраняются в `uploads/`, данные — в MySQL.

## 🤖 AI-помощник для добавления фильмов

Умный сценарий добавления работает через того же бота (кнопка
**«🤖 AI: добавить фильм по постеру»** в `/admin`). Ключ OpenAI используется
**только на сервере** (PHP) и никогда не попадает в JavaScript, Mini App или
Telegram-клиент.

**Как это работает:**
1. Админ отправляет **постер**.
2. Сервер автоматически: сохраняет изображение, определяет ориентацию, делает
   **Smart Crop** (с защитой лиц и названия через AI-фокус), создаёт
   **Poster / Thumbnail / Banner / Background**, конвертирует в **WebP** и
   оптимизирует качество. Если постер вертикальный, широкий баннер собирается
   автоматически (размытый фон + постер, без обрезки лиц и названия).
3. AI распознаёт фильм по постеру. Если не удаётся — просит ввести название.
4. AI **сам заполняет карточку**: название, оригинальное название, описание,
   год, жанры, страна, режиссёр, актёры, длительность, возраст, рейтинг, тип,
   статус, ключевые слова, похожие фильмы. Неизвестные поля остаются пустыми —
   их можно дозаполнить.
5. Опционально прикрепляется **видео (Telegram File ID) или ссылка** — большие
   видеофайлы на сервере **не хранятся**.
6. Показывается предпросмотр карточки с кнопками **✅ Опубликовать /
   ✏ Редактировать / ❌ Отмена**. После публикации фильм сразу появляется на
   главной (Hero-баннер, Новинки, Категории, Поиск) без ручного обновления.

> Если ключ OpenAI не задан — постер всё равно обрабатывается автоматически,
> а карточку можно заполнить вручную через «✏ Редактировать».

**Миграция БД (для уже существующей базы):**
```bash
mysql -u root -p cinema < database/ai_upgrade.sql
```
(Новые установки уже содержат нужные поля в `schema.sql`.)

**Просмотр (▶ Смотреть):** Mini App отправляет `movie_id` в API; если у фильма
есть Telegram File ID — бот отправляет видео прямо в чат пользователю; иначе
возвращается ссылка. Веб-сервер большие видео не отдаёт.

## ⚡ Сборка ассетов (минификация)

```bash
php assets/build.php   # создаёт assets/css/app.min.css и assets/js/app.min.js
```
Mini App автоматически использует `.min`-версии, если они есть (с cache-busting
`?v=mtime`). Дополнительно `assets/.htaccess` включает gzip и долгое
кэширование. Изображения отдаются в WebP, с lazy-loading и skeleton-лоадерами.

## 🔌 REST API

Базовый адрес: `api/index.php?route=<endpoint>` (работает без mod_rewrite).
При наличии `mod_rewrite` доступен также `api/<endpoint>`.

| Метод | Endpoint | Описание |
|---|---|---|
| GET | `home` | Всё для главной: баннеры + рельсы разделов |
| GET | `movies` | Список с фильтрами (`category,genre,year,min_rating,flag,sort,q,limit,offset`) |
| GET | `movie?id=` | Карточка фильма + похожие |
| GET | `genres` | Список жанров |
| GET | `search?q=` | Живой поиск + фильтры |
| GET | `announcements` | Активные анонсы |
| GET | `banners` | Слайды hero-баннера |
| GET/POST | `favorites` | Список / переключение избранного |
| GET/POST | `history` | «Продолжить просмотр» / запись прогресса |
| POST | `watch` | Открыть просмотр (учёт просмотра + история) |
| GET/POST | `profile` | Профиль пользователя |

Запросы к пользовательским эндпоинтам (favorites/history/profile) авторизуются
через `initData` Telegram WebApp (заголовок `X-Telegram-Init-Data`), подпись
проверяется по официальному алгоритму HMAC-SHA256.

## 🔒 Безопасность

- Все SQL — через **PDO prepared statements** (защита от инъекций).
- Экранирование вывода на фронте (`esc()`) — защита от XSS.
- Проверка подписи Telegram `initData` + секретный токен вебхука.
- Папки `config/`, `logs/`, `database/` закрыты через `.htaccess`.
- В `uploads/` отключено исполнение PHP.

## 🚀 Производительность

Lazy-loading изображений (IntersectionObserver), skeleton-лоадеры,
infinite scroll, авто-ротация hero, кэш-дружественные запросы.
Для продакшена рекомендуется минифицировать `assets/css/app.css` и
`assets/js/app.js` и отдавать постеры в WebP.

## 🖥️ Локальная проверка

```bash
php -S localhost:8000 -t project
# API:     http://localhost:8000/api/index.php?route=home
# MiniApp: http://localhost:8000/miniapp/
```
(Полноценно Mini App работает внутри Telegram, где доступен `initData`.)
