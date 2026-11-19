# Бэкенд магазина (Python FastAPI + PostgreSQL)

## Что уже работает (шаг 1)
- Регистрация, вход, выход, «кто я» — пароль хранится как хеш argon2, сессия в cookie (HttpOnly).
- Защита от подбора пароля: после 5 ошибок — пауза 10 минут.
- Подключение к поставщику **только на чтение** (денег не тратит):
  - каталог пополнений игр, пакеты и поля формы (Player ID, Zone ID…);
  - цены **с вашей наценкой** (закупочная цена покупателю не показывается, картинки правообладателей не передаются);
  - проверка ID игрока (ник и регион);
  - цены Telegram Stars и Premium.
- Админка: статус ключа и подписки у поставщика, ваш баланс у поставщика, наценка в %.

## Запуск на своём компьютере
```bash
cd shop-backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env        # заполнить: DATABASE_URL, SECRET_KEY, SUPPLIER_API_KEY, ADMIN_EMAILS
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --port 8000
```
Документация API: http://localhost:8000/api/docs

## Тесты
```bash
.venv/bin/python -m pytest -q                       # на SQLite
TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q   # на PostgreSQL
```
Поставщик в тестах подменён: тесты не ходят в интернет и не тратят деньги.

## Безопасность
- Все ключи и пароли — только в `.env` (он в .gitignore).
- Ключ поставщика не пишется в логи и не возвращается в ответах.
