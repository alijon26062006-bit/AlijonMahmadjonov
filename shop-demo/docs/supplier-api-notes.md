# Заметки по API поставщика (для будущего сервера)

Источник: `supplier-openapi.json` (OpenAPI 3.0.3, версия 0.1.0), сохранён 19.11.2026.
На сайте имя поставщика не показываем.

## Доступ
- База: `https://api.fzr.cards/api/v2/…`
- Ключ: заголовок `X-API-Key: fc_…` (или `Authorization: Bearer fc_…`). Хранить только в `.env`.
- Без активной подписки API отвечает 403 `subscription_inactive`.
- Ответы: `{ ok: true, … }` или `{ ok: false, error, code }`.

## Что берём для магазина
| Раздел | Каталог | Заказ |
|---|---|---|
| Пополнение игр | `GET /topups`, `GET /topups/offers?category_id=` (offers + `fields` формы) | `POST /topups/order` {category_id, offer_id, fields} |
| Проверка ID игрока | `GET /topups/validate-id` (список игр и полей) | `POST /topups/validate-id` → valid, player_name, region |
| Подарочные карты | `GET /giftcards`, `GET /giftcards/cards?category_id=` (stock, min/max qty) | `POST /giftcards/order` {category_id, card_id, quantity} |
| Ключи игр | `GET /gamekeys`, `GET /gamekeys/keys`, `GET /gamekeys/region-restriction` | `POST /gamekeys/order` |
| Steam пополнение | `GET /steam-topup/rates`, `POST /steam-topup/check-login` | `POST /steam-topup/order` |
| Steam гифты | `GET /steam-gifts/games` (лимит 1 запрос / 3 мин — кэшировать), `GET /steam-gifts/games/{appid}` | `POST /steam-gifts/order` {invite_url, sub_id, app_id, region} |
| Telegram | `GET /telegram/stars` (price_per_star, min/max), `GET /telegram/premium` (3/6/12) | `POST /telegram/stars/buy`, `POST /telegram/premium/buy` |
| Ручные услуги | `GET /manual-services`, `GET /manual-services/{id}/offers` | `POST /manual-services/order`, чат заказа |

- Списание с баланса поставщика сразу, дальше `processing` → выполнен или возврат.
- `Idempotency-Key` (до 255 символов) поддерживается на заказах — отправлять всегда (ID нашего заказа), чтобы повтор запроса не списал дважды.
- Статус: `GET /orders/{orderId}`, список `GET /orders?page&limit`. Схема объекта заказа в документации не описана — уточнить на живом ответе.
- Обложки: `include_ui=1` добавляет `imageurl` (это картинки правообладателей — на сайте не используем).

## Баланс у поставщика
- `GET /balance` (USD, 4 знака), `GET /transactions`.
- Пополнение баланса поставщика: `POST /payments/create` {method: "usdt", amount} → ссылка на страницу оплаты;
  `POST /payments/direct` (нужно одобрение) → адрес + uniqueAmount + memo, 30 минут.
  Лимиты: 3 счёта в минуту, не больше 3 неоплаченных на одну сумму.

## Вебхук
- `PUT /account/webhook` {url, enabled}, секрет HMAC (`/secret/regenerate`), `POST /account/webhook/test`, `GET /account/webhook/deliveries`.
- Названия событий, формат тела и заголовок подписи в документации НЕ описаны (есть только `webhook.test`). Пока нет ответа поставщика — опрашивать `GET /orders/{id}`.
