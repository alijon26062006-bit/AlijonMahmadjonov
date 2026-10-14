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
.venv/bin/mypy              # строгая проверка типов (src и tests)
```

## Что уже есть

- `src/wbm/wb_client/` — единственный модуль доступа к WB API:
  белый список методов «только чтение» (две линии защиты), очередь по лимитам WB,
  повтор при 429 / 5xx / сбоях сети, таймауты, песочница через `WB_SANDBOX`, логи без токена.
- `src/wbm/wb_client/token_check.py` — проверка токена при подключении магазина.
- `src/wbm/logging_setup.py` — логи с вычисткой токенов, ключей и паролей.
