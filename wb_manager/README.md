# AI-менеджер для продавцов Wildberries (v1 — только анализ)

План и архитектура — [docs/PLAN.md](docs/PLAN.md). Что подтверждено в документации WB —
[docs/WB_API.md](docs/WB_API.md).

## Запуск

```bash
cp .env.example .env            # заполнить: TELEGRAM_BOT_TOKEN, DATABASE_URL, FERNET_KEYS, ANTHROPIC_API_KEY
.venv/bin/alembic upgrade head  # таблицы в MySQL
.venv/bin/python -m wbm.bot     # Telegram-бот
.venv/bin/python -m wbm.worker  # фоновые анализы (отдельный процесс)
```

## Разработка

```bash
cd wb_manager
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

.venv/bin/pytest            # тесты
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/mypy              # строгая проверка типов (src, tests, migrations)

# Те же тесты базы на настоящем MySQL 8 (иначе только SQLite):
WBM_TEST_MYSQL_URL="mysql+aiomysql://wbm:пароль@127.0.0.1:3306/wbm_test?charset=utf8mb4" .venv/bin/pytest

# Миграции базы (адрес — DATABASE_URL):
.venv/bin/alembic upgrade head
```

## Что уже есть

- `src/wbm/wb_client/` — единственный модуль доступа к WB API:
  белый список методов «только чтение» (две линии защиты), очередь по лимитам WB,
  повтор при 429 / 5xx / сбоях сети, таймауты, песочница через `WB_SANDBOX`, логи без токена.
- `src/wbm/wb_client/token_check.py` — проверка токена при подключении магазина.
- `src/wbm/logging_setup.py` — логи с вычисткой токенов, ключей и паролей.
- `src/wbm/db/` — модели MySQL (SQLAlchemy 2), репозитории с доступом только к своим
  данным, очередь анализов в базе (SKIP LOCKED), миграции Alembic в `migrations/`.
- `src/wbm/security/` — шифрование токенов WB (Fernet, со сменой ключа), пароли argon2id.
  Новый ключ: `python -m wbm.security.keygen`.
- `src/wbm/domain/` — данные магазина в нашем формате (не зависят от полей WB).
- `src/wbm/checks/` — 10 проверок, пороги в `thresholds.py`, запуск в `runner.py`:
  без данных → «нет данных», без себестоимости → «нужна себестоимость», ошибка проверки
  не роняет остальные.
- `src/wbm/analysis/` — поиск аномалий в данных до выводов (оговорка в отчёте), сохранение
  результатов в базу.
- `src/wbm/report/` — текст отчёта. Claude (`ANTHROPIC_MODEL`, по умолчанию `claude-opus-5-5`)
  получает только готовые цифры; любое число в его тексте, которого нет в данных, — текст
  отбрасывается и заменяется шаблоном. Без ключа, при отказе или сбое Claude — шаблоны.
  Включён серверный запасной вариант Anthropic (`fallbacks: "default"`) на случай отказа модели.
- `src/wbm/bot/` — Telegram-бот (интерфейс v1): вход по Telegram + номер телефона, токен в чат
  (сообщение сразу удаляется, токен хранится зашифрованным), себестоимость файлом, /analyze,
  /history с PDF, /shops. Логика — в `services.py`, обработчики — в `handlers.py`.
- `src/wbm/worker/` — очередь анализов: прогресс в Telegram, итог (топ-5) и полный отчёт PDF.
- `src/wbm/collectors/` — загрузка данных WB; сборщики добавляются по мере сверки документации.
- `src/wbm/costs.py` — файл себестоимости (CSV/Excel).
