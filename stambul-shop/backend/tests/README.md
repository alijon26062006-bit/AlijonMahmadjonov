# Проверки

Идут на настоящих PostgreSQL и Redis: заглушки прячут ровно те ошибки, ради
которых всё и затевается — блокировки строк, уникальные индексы, поведение
JSONB.

```bash
docker compose up -d db redis
docker compose run --rm migrate

cd backend/tests
DATABASE_URL=postgresql+asyncpg://shop:shop@localhost:5432/shop \
REDIS_URL=redis://localhost:6379/1 \
for t in test_auth test_shop test_studio test_wizard; do python3 $t.py; done
```

- `test_auth.py` — вход по номеру с кодом от бота, вход через Google,
  привязка Telegram, слияние аккаунтов, ограничение частоты.
- `test_shop.py` — товар с размерами, витрина, корзина, оформление, гонка
  двух покупателей за последней вещью, цепочка статусов, возврат склада.
- `test_studio.py` — стиль каталога, выбор фона под яркость товара, хранение
  ключа стороннего сервиса, переключение «оригинал / обработанная».
- `test_wizard.py` — свои разделы из бота и чистка черновика от модели:
  выдуманный раздел отбрасывается, цвет приводится к списку каталога.
