# API проверки ника

Готовый HTTP-сервис: принимает ID игрока — возвращает ник. Нужен, чтобы
подключить проверку ника к любому другому проекту (сайт, второй бот,
приложение), не отдавая туда ключ FireLoot.

* Зависимостей нет — только `python3`, ставить ничего не надо.
* Работает отдельной службой, бот-магазин не трогает.
* Заказы не создаются никогда: сервис умеет только `/validate` и
  `/telegram/check`. Потратить деньги через него невозможно.

## Запуск

```bash
bot nick --service     # поставить службой (работает 24/7, переживает перезагрузку)
bot nick --test        # проверить, что отвечает
bot nick --log         # логи
bot nick --stop        # остановить
bot nick               # запустить в терминале, чтобы посмотреть вживую
```

При первом запуске в `.env` сам создаётся `NICK_API_TOKEN` — ключ доступа к
этому сервису. Его и адрес сервера отдаёте другому проекту. Команда
`bot nick --service` печатает то и другое.

## Запросы

Ключ доступа — в заголовке `X-Api-Key`.

```bash
# Free Fire СНГ
curl -H "X-Api-Key: ВАШ_ТОКЕН" \
     "http://ВАШ_IP:8081/nick?game=ff&id=123456789"

# Mobile Legends — нужен номер сервера
curl -H "X-Api-Key: ВАШ_ТОКЕН" \
     "http://ВАШ_IP:8081/nick?game=mlbb&id=123456789&server=2001"

# То же самое через POST
curl -X POST -H "X-Api-Key: ВАШ_ТОКЕН" -H "Content-Type: application/json" \
     -d '{"game":"pubg","id":"5123456789"}' \
     "http://ВАШ_IP:8081/nick"
```

Ответ, когда ник найден:

```json
{"ok": true, "game": "ff", "title": "Free Fire (СНГ)",
 "id": "123456789", "nickname": "AlijonTJ", "cached": false}
```

Ответ, когда ID неверный (HTTP 404):

```json
{"ok": false, "game": "ff", "id": "1",
 "code": "invalid_uid", "error": "ID игрока неверный"}
```

Проверяйте поле `ok`. Текст из `error` можно показывать человеку как есть.

## Эндпоинты

| Путь | Что делает | Нужен ключ |
|---|---|---|
| `GET /nick?game=&id=&server=` | проверка ника | да |
| `POST /nick` (JSON) | то же самое | да |
| `GET /games` | список игр и какие поля нужны | да |
| `GET /health` | жив ли сервис | нет |

## Игры

| `game` | Игра | Номер сервера |
|---|---|---|
| `ff` | Free Fire (СНГ) | — |
| `ffid` | Free Fire (Индонезия) | — |
| `pubg` | PUBG Mobile | — |
| `mlbb` | Mobile Legends | нужен |
| `mlbbcis` | Mobile Legends (СНГ) | нужен |
| `hok` | Honor of Kings | — |
| `bs` | Blood Strike | — |
| `mr` | Marvel Rivals | — |
| `tg` | Telegram (Stars), `id` = username | — |

Понимаются и привычные написания: `freefire`, `pubgm`, `ml`, `stars` и т. д.
Актуальный список всегда отдаёт `GET /games`.

Новая игра добавляется одной строкой в `nickapi/games.py` — нужен любой `sku`
этой игры из `bot api --catalog`.

## Коды ошибок

| `code` | Значит |
|---|---|
| `invalid_uid` / `invalid_username` | ID или username неверный |
| `not_found` | аккаунт не найден |
| `unknown_game` | такой игры нет в списке |
| `server_required` | для этой игры нужен `server` |
| `region_unsupported` | регион аккаунта не поддерживается |
| `product_not_found` | игра недоступна на вашем ключе FireLoot |
| `rate_limited` | слишком много запросов |
| `service_unavailable` | поставщик не ответил |
| `unauthorized` | ключ FireLoot неверный |

## Подключение из кода

Python:

```python
import requests

def nickname(game: str, player_id: str, server: str = "") -> str | None:
    r = requests.get(
        "http://ВАШ_IP:8081/nick",
        params={"game": game, "id": player_id, "server": server},
        headers={"X-Api-Key": "ВАШ_ТОКЕН"},
        timeout=35,
    )
    data = r.json()
    return data["nickname"] if data.get("ok") else None
```

JavaScript:

```js
async function nickname(game, id, server = "") {
  const url = new URL("http://ВАШ_IP:8081/nick");
  url.search = new URLSearchParams({ game, id, server });
  const r = await fetch(url, { headers: { "X-Api-Key": "ВАШ_ТОКЕН" } });
  const data = await r.json();
  return data.ok ? data.nickname : null;
}
```

PHP:

```php
function nickname($game, $id, $server = '') {
  $url = 'http://ВАШ_IP:8081/nick?' . http_build_query(compact('game','id','server'));
  $ctx = stream_context_create(['http' => ['header' => "X-Api-Key: ВАШ_ТОКЕН\r\n",
                                           'timeout' => 35, 'ignore_errors' => true]]);
  $data = json_decode(file_get_contents($url, false, $ctx), true);
  return !empty($data['ok']) ? $data['nickname'] : null;
}
```

## Настройки (`.env`)

| Переменная | По умолчанию | Зачем |
|---|---|---|
| `NICK_API_TOKEN` | создаётся сам | ключ доступа к сервису |
| `NICK_API_PORT` | `8081` | порт |
| `NICK_API_HOST` | `0.0.0.0` | `127.0.0.1` — только с этого сервера |
| `NICK_API_KEY` | берётся `SHOP_SUPPLIER_KEY` | ключ FireLoot |
| `NICK_API_CACHE` | `300` | сколько секунд помнить найденный ник |
| `NICK_API_RATE` | `60` | запросов в минуту с одного адреса |
| `NICK_API_CORS` | выкл. | разрешить запросы прямо из браузера |

## Безопасность

* Найденные ники кешируются на 5 минут, поэтому одинаковые запросы не
  дёргают поставщика и не съедают лимит.
* Один адрес — не больше 60 запросов в минуту, дальше `429`.
* Ключ FireLoot наружу не уходит: другой проект знает только
  `NICK_API_TOKEN`, который можно в любой момент поменять в `.env`.
* `NICK_API_CORS` включайте, только если запросы идут прямо из браузера:
  тогда токен будет виден пользователям сайта. Правильнее ходить со своего
  сервера.
