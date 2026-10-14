# AI-менеджер для продавцов Wildberries (v1 — только анализ)

План и архитектура — [docs/PLAN.md](docs/PLAN.md). Что подтверждено в документации WB —
[docs/WB_API.md](docs/WB_API.md).

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
