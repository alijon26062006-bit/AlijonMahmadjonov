# AI-менеджер для продавцов Wildberries — план v1 (только анализ)

Проект живёт в папке `wb_manager/` и не затрагивает остальной репозиторий (сайт, бот учёта денег).

## 1. Принципы архитектуры

- **Только чтение WB.** Все запросы идут через `wb_client`. В нём есть белый список методов
  `(HTTP-метод, хост, путь)`. Любой запрос не из списка падает с ошибкой ещё до отправки.
  POST разрешён только для методов, которые по документации читают данные (например, список карточек).
- **Слои:** `wb_client` (транспорт) → `collectors` (загрузка данных в нормализованные модели)
  → `checks` (детерминированные проверки) → `report` (сборка + текст от Claude) → `web` / `bot`.
- **Расширяемость.** Проверки регистрируются через реестр (`@register_check`). Будущие функции
  (автоответы, цены, реклама) появятся отдельными модулями `actions/` с отдельным белым списком
  методов на запись и отдельным типом токена. Код анализа при этом не меняется.
- **Частичные данные.** Каждый коллектор возвращает `DataResult[T]` со статусом `ok | empty | error | anomaly`.
  Проверка заранее объявляет, какие наборы данных ей нужны. Если их нет, она получает статус «нет данных»
  и не падает.
- **Claude не считает.** На вход ему подаётся готовый JSON с фактами. Ответ проверяется: каждое число в тексте
  должно встречаться во входных фактах, иначе используется шаблонный текст без LLM.

## 2. Структура

```
wb_manager/
├── pyproject.toml            # зависимости, ruff, mypy (strict), pytest
├── .env.example
├── alembic.ini
├── migrations/               # Alembic
├── docker/                   # Dockerfile, nginx.conf, certbot
├── docker-compose.yml        # app, worker, mysql, nginx (+ certbot)
├── docs/                     # PLAN.md, DEPLOY.md, WB_API.md (методы и лимиты)
├── src/wbm/
│   ├── config.py             # pydantic-settings, все пороги и настройки
│   ├── logging.py            # структурные логи + фильтр секретов
│   ├── security/             # Fernet-шифрование токенов, хеш паролей (argon2), CSRF
│   ├── wb_client/
│   │   ├── client.py         # httpx.AsyncClient, ретраи 429/5xx, таймауты
│   │   ├── ratelimit.py      # token-bucket по каждой группе лимитов WB
│   │   ├── endpoints.py      # белый список read-only методов (+ sandbox-хосты)
│   │   ├── errors.py
│   │   └── api/              # тонкие обёртки: content.py, prices.py, stats.py, feedbacks.py, adverts.py, finance.py
│   ├── domain/               # Pydantic-модели: Product, Stock, Order, Sale, Feedback, Campaign, FinanceRow, CostPrice
│   ├── collectors/           # загрузка + нормализация + детекция аномалий
│   ├── checks/
│   │   ├── base.py           # Check, CheckResult, Severity, Finding, реестр
│   │   ├── thresholds.py     # пороги по умолчанию (переопределяются из .env/БД)
│   │   ├── c01_stock_out.py … c10_suspicious_deductions.py
│   ├── analysis/runner.py    # оркестрация: сбор → аномалии → проверки → отчёт
│   ├── report/               # builder.py, llm.py (Anthropic), validate.py, templates
│   ├── db/                   # SQLAlchemy 2 (async, asyncmy), модели, репозитории
│   ├── web/                  # FastAPI: роуты, Jinja2-шаблоны, адаптивный CSS, HTMX для прогресса
│   ├── worker/               # фоновые задачи (очередь заданий в MySQL, без Redis)
│   └── bot/                  # aiogram 3: /start, привязка, /analyze
└── tests/                    # unit на проверки, wb_client с respx-моками, web, db
```

**Очередь задач.** Делаю простую очередь на таблице `analysis_runs` в MySQL: worker забирает задачи
через `SELECT … FOR UPDATE SKIP LOCKED`. Redis не нужен, на одном VPS это проще. Если позже понадобится, можно перейти на arq/Redis.

## 3. Модель данных (черновик)

- `users`: id, email, password_hash, created_at, tg_chat_id, tg_link_code
- `shops`: id, user_id, name, wb_token_encrypted, token_checked_at, token_scopes, sandbox
- `cost_prices`: shop_id, vendor_code/nm_id, cost, uploaded_at
- `analysis_runs`: id, shop_id, status, progress, started/finished, error
- `analysis_datasets`: run_id, dataset, status (ok/empty/error/anomaly), rows, message
- `findings`: run_id, check_id, severity, title, products (JSON), facts (JSON), reason, recommendation, text_llm
- `login_attempts`: ограничение попыток входа

Сырые ответы WB в БД не хранятся (только агрегаты и находки). Так база меньше и в ней меньше персональных данных.

## 4. Проверки (пороги настраиваются)

| # | Проверка | Данные | Ключевая логика |
|---|---|---|---|
| 1 | Закончился / скоро закончится | остатки, заказы | дни запаса = остаток / ср. заказов в день (14 дн.); <7 — критично, <14 — важно |
| 2 | Падение заказов | заказы | период N vs предыдущий N; падение ≥30% при мин. объёме |
| 3 | Отзывы/вопросы без ответа | отзывы, вопросы | негатив (≤3★) без ответа > X ч — критично |
| 4 | Частые жалобы | отзывы | словари тем (размер, цвет, качество, брак, упаковка), доля ≥ порога |
| 5 | Возвраты и отмены | заказы, продажи | % отмен/возвратов выше порога и выше среднего по магазину |
| 6 | Продажи в минус | фин. отчёт, себестоимость | выручка − комиссия − логистика − хранение − себестоимость < 0; без себестоимости — «нужна себестоимость» |
| 7 | Неэффективная реклама | кампании, статистика | ДРР > порога; расход > X без заказов |
| 8 | Залежавшийся товар | остатки, продажи, хранение | нет продаж N дней и стоимость хранения > порога |
| 9 | Качество карточек | карточки, ошибки карточек | пустые характеристики, описание < N символов, мало фото, ошибки |
| 10 | Подозрительные удержания | фин. отчёт, приёмка | штрафы, логистика выше медианы, расхождения приёмки, исчезновение остатков без продаж |

**Аномалии** (до проверок): ноль заказов при ненулевой истории, резкий обрыв ряда по датам,
пустой ответ при непустых остатках. Такие наборы данных помечаются в отчёте, и зависящие от них выводы снабжаются оговоркой.

## 5. Этапы

1. Структура и план ← **сейчас**
2. `wb_client` + тесты (respx)
3. БД, модели, Alembic
4. Проверки 1–10 + тесты
5. Отчёт (Claude)
6. Веб-интерфейс
7. Telegram-бот
8. Docker, nginx, HTTPS, DEPLOY.md

## 6. Методы WB API, которые нужно подтвердить по документации

Из моей среды dev.wildberries.ru недоступен. Ниже то, что я знаю. **Каждый пункт помечен «сверить»**,
и в код он попадёт только после подтверждения.

| Данные | Хост | Метод (по моим знаниям) | Сверить |
|---|---|---|---|
| Проверка токена | все | `GET /ping` | лимиты ping |
| Инфо продавца | common-api | `GET /api/v1/seller-info` | |
| Карточки | content-api | `POST /content/v2/get/cards/list` (чтение, курсор) | актуальная версия |
| Ошибки карточек | content-api | `GET /content/v2/cards/error/list` | не сменился ли метод |
| Цены/скидки | discounts-prices-api | `GET /api/v2/list/goods/filter` | |
| Остатки | statistics-api / seller-analytics-api | `GET /api/v1/supplier/stocks` или отчёт `warehouse_remains` (асинхронный) | какой метод актуален |
| Заказы / продажи | statistics-api | `GET /api/v1/supplier/orders`, `/api/v1/supplier/sales` | лимит 1 запрос/мин? |
| Возвраты | seller-analytics-api | `GET /api/v1/analytics/goods-return` | |
| Отзывы / вопросы | feedbacks-api | `GET /api/v1/feedbacks`, `GET /api/v1/questions` | |
| Реклама | advert-api | список кампаний + `fullstats` | v2/v3, GET/POST |
| Фин. отчёт | statistics-api | `GET /api/v5/supplier/reportDetailByPeriod` | |
| Платное хранение | seller-analytics-api | `paid_storage` (асинхронный отчёт) | |
| Приёмка / штрафы | seller-analytics-api | `acceptance_report`, `antifraud-details`, `incorrect-attachments` | |
| Sandbox | `*-sandbox.wildberries.ru` | | какие категории есть в sandbox |
