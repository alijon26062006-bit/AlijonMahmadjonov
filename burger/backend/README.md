# Бэкенд The Burger

Сервер сайта: меню в базе, админка для заведения, приём заказов.
Ставится на любой недорогой VPS, тяжёлого ничего не нужно.

- **API для сайта** — `/api/menu`, `/api/orders`
- **Админка** — `/admin`: блюда, цены, фото, наличие, заказы, настройки
- **База** — SQLite, один файл `data/burger.db`
- **Уведомления** — заказ приходит в Telegram, если настроен бот

Цены и суммы считает сервер. Данные из браузера для этого не используются:
их можно подделать.

## Запуск на своей машине

```bash
cd burger/backend
pip install -r requirements.txt
cp .env.example .env          # заполнить пароль и ключ

export ADMIN_PASSWORD="ваш-пароль"
export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
uvicorn app:app --reload --port 8000
```

- сайт-API: http://127.0.0.1:8000/api/menu
- админка: http://127.0.0.1:8000/admin

При первом запуске база наполняется меню из `seed_data.py` — 25 блюд,
5 разделов, районы доставки. Дальше всё правится в админке.

## Подключить сайт к серверу

В `burger/js/main.js` первая строка:

```js
const API = 'https://api.theburger.tj';   // адрес бэкенда
```

Пусто — сайт работает сам по себе на встроенном меню и отправляет заказ
текстом в Telegram. Заполнено — меню приходит с сервера, заказ падает в базу.
Если сервер не ответил, сайт молча показывает встроенное меню: пустой
страницы клиент не увидит.

## Настройки

Задаются переменными окружения (файл `.env` или systemd).

| Переменная | Зачем |
|------------|-------|
| `ADMIN_PASSWORD` | пароль в админку. **Обязательно смените** |
| `SECRET_KEY` | подпись входа. Длинная случайная строка |
| `TG_TOKEN` | токен бота у @BotFather — чтобы заказы падали в Telegram |
| `TG_ADMIN_CHAT` | куда слать: ваш id у @userinfobot или id группы |
| `ALLOWED_ORIGINS` | адреса сайта через запятую. На бою укажите свой домен вместо `*` |
| `ORDER_COOLDOWN` | секунд между заказами с одного адреса, по умолчанию 20 |

## На сервере

Пример для Ubuntu: systemd + Caddy для HTTPS.

`/etc/systemd/system/burger.service`:

```ini
[Unit]
Description=The Burger
After=network.target

[Service]
WorkingDirectory=/srv/burger/backend
EnvironmentFile=/srv/burger/backend/.env
ExecStart=/usr/bin/python3 -m uvicorn app:app --host 127.0.0.1 --port 8000
Restart=always
User=www-data

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now burger
```

`Caddyfile` — HTTPS оформляется сам:

```
api.theburger.tj {
    reverse_proxy 127.0.0.1:8000
}
```

## Резервная копия

Вся база — один файл. Копировать раз в сутки:

```bash
sqlite3 /srv/burger/backend/data/burger.db ".backup /srv/backup/burger-$(date +%F).db"
```

Фото лежат в `uploads/` — их тоже в копию.

## Проверки

```bash
python3 -m pytest tests/ -q
```

14 проверок: подсчёт цены на сервере, доставка по районам, бесплатная
доставка от порога, минимальный заказ, отказ по несуществующему блюду,
защита админки, вход с кириллическим паролем, скрытие блюда из наличия.
