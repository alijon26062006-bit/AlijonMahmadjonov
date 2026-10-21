# Donatix API для партнёров (v1)

Полное описание для разработчика, который подключает бота или сайт к Donatix.
Все запросы — по HTTPS, ответы — JSON.

- **Базовый адрес:** `https://donatix.tj/api/v1`
- **Ключ:** заголовок `X-API-Key: dx_live_...` (или `Authorization: Bearer dx_live_...`).
  Ключ даёт доступ к аккаунту партнёра: баланс, заказы, покупки. Храните его только на сервере, не в коде клиента и не в чате.
- **Успех:** `{"ok": true, ...}`. **Ошибка:** `{"ok": false, "error": "текст", "code": "код"}`.
- **Лимиты:** ограничение частоты запросов. При `429` подождите `Retry-After` секунд.

## Коды ошибок (общие)
| HTTP | code | Что делать |
|---|---|---|
| 401 | `unauthorized` | ключ неверный, отозван или перевыпущен. Возьмите новый ключ в кабинете |
| 403 | `account_blocked` | аккаунт заблокирован |
| 402 | `insufficient_balance` | пополните баланс |
| 400 | `order_failed` | заказ не создан, деньги не списаны или возвращены |
| 404 | `order_not_found` | заказа нет или он не ваш |
| 429 | `rate_limited` | слишком много запросов, подождите `Retry-After` |
| 503 | `service_unavailable` | раздел временно выключен |

## 1. Аккаунт
- `GET /me` — данные аккаунта.
- `GET /balance` — баланс в USD: `{"ok": true, "balance": "12.3400", "currency": "USD"}`.
- `GET /transactions?page=1&limit=20` — движение денег.

## 2. Каталог и заказы игр, Stars, Premium, Steam, подарочных карт
- `GET /categories` — все игры и сервисы: `category_id`, `kind`, `products` (сколько пакетов), `image_url` (обложка).
- **Картинки:** `image_url` у игр и товаров — полная ссылка на картинку на `donatix.tj` (например, `https://donatix.tj/media/ab12cd.png`).
  Скачивайте её или ставьте в свой сайт напрямую. Если картинки ещё нет, поле равно `null`: покажите свою заглушку.
- `GET /products?kind=&category_id=&q=&limit=100&offset=0` — товары с вашей ценой.
  **За один запрос не больше 500 товаров** (по умолчанию 100). Листайте через `offset`, пока `items` не пустой.
- `GET /products/{product_id}` — один товар.
- `POST /accounts/check` — проверка аккаунта игрока (ID) до заказа.
- `POST /orders` — заказ: `{"product_id": "...", "quantity": 1, "fields": {...}}`. Заголовок `Idempotency-Key` защищает от двойного заказа.
- `GET /orders?page=&limit=&status=`, `GET /orders/{order_id}` — заказы.

Виды товаров (`kind`): `topup` (пополнение игр), `telegram_stars`, `telegram_premium`, `steam_topup`, `steam_gift`, `gift_card`, `game_key`.

## 3. Пополнение баланса
- `GET /payments/methods` — способы оплаты.
- `POST /payments` — заявка на пополнение, `POST /payments/{id}/receipt` — чек.
- `GET /payments`, `GET /payments/{id}` — статус.

## 4. Виртуальные номера (коды из SMS)
Цены как на сайте. Списание с баланса. Если номер не получился или код не пришёл, деньги возвращаются сами.

- `GET /numbers/services` — сервисы: `telegram`, `whatsapp`, `tiktok`, `instagram`, `google`, `facebook`, `discord`, `viber`.
- `GET /numbers/countries?service=telegram` — страны с ценой (`price_usd`) и количеством номеров (`available`).
- `POST /numbers/orders` — купить: `{"service": "telegram", "country": "indonesia"}`.
  Ответ: `order` с `id`, `phone`, `status`, `code`, `expires`.
- `GET /numbers/orders/{id}` — **опрашивайте каждые 5–10 секунд**. Когда `code` заполнен, номер готов.
  Статусы: `PENDING` (ждём код), `RECEIVED` (код пришёл), `FINISHED`, `CANCELED`, `TIMEOUT` (код не пришёл, деньги вернулись), `BANNED` (номер отклонён, деньги вернулись).
- `POST /numbers/orders/{id}/cancel` — отмена (если код не нужен).
- `GET /numbers/orders?limit=20` — свои заказы.

## 5. Подарки Telegram
Цена как на сайте. Списание с баланса.

- `GET /gifts` — подарки: `gift_id`, `stars`, `emoji`, `image`, `price_usd`, `left` (сколько осталось у лимитированных), `total`.
- `POST /gifts/orders` — отправить подарок:
  `{"gift_id": "g15", "recipient": "@username", "text": "подпись до 128 символов"}`.
  - Если получатель уже нажимал Start в боте Donatix, подарок уходит сразу (`status: "paid"`).
  - Если не нажимал, в ответе будет `status: "awaiting_recipient"` и `link`. Отправьте ссылку получателю: он нажмёт Start и получит подарок.
  - `recipient` можно не указывать, тогда сразу будет только ссылка.
- `GET /gifts/orders/{id}` — статус: `paid`, `sent`, `awaiting_recipient`, `failed`, `refunded`.

## 6. Боты для гильдии (Glory, Free Fire)
- `GET /glory/regions` — регионы и цена (одна для всех регионов).
- `POST /glory/orders` — запуск ботов для клана.
- `GET /glory/orders/{id}` — очки клана и статус (обновлять каждые 15–30 секунд).
- `POST /glory/orders/{id}/stop` — остановить. После запуска деньги не возвращаются, можно только остановить.

## 7. Webhook
Donatix может сам присылать уведомления о заказах на ваш адрес. Адрес и секрет задаются в кабинете (раздел API).
Каждое сообщение содержит заголовки `X-Donatix-Timestamp` и `X-Donatix-Signature`.
Подпись: HMAC-SHA256 (hex) от строки `<timestamp>.<тело запроса>` секретом вебхука. Проверяйте её перед тем, как доверять сообщению.

## Пример на Python (баланс и список номеров)
```python
import os, json, urllib.request
BASE = "https://donatix.tj/api/v1"
KEY = os.environ["DONATIX_KEY"]          # ключ храните в переменной окружения, не в коде

def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method,
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"X-API-Key": KEY, "Content-Type": "application/json",
                                          "User-Agent": "MyBot/1.0"})   # User-Agent обязателен
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

print(call("GET", "/balance"))
order = call("POST", "/numbers/orders", {"service": "telegram", "country": "indonesia"})["order"]
print(call("GET", f"/numbers/orders/{order['id']}"))
```

## Важно
- Не отправляйте ключ в чат, в публичный репозиторий или в адрес в браузере.
- Всегда задавайте `User-Agent`. Запросы без него могут блокироваться защитой Cloudflare (код 1010).
- Для покупок используйте уникальные `Idempotency-Key` (для заказов игр) и не повторяйте покупку без проверки статуса.
