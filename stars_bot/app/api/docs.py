"""Страница документации API.

Отдаётся тем же сервером, что и сам API: разработчик открывает адрес,
который ему дали, и сразу видит, что делать. Отдельного сайта для этого
не нужно, а документация, лежащая не там же, где API, устаревает первой.

Страница собирается строкой — без шаблонизатора и без внешних файлов:
лишняя зависимость ради одной страницы не стоит того, а картинок и
шрифтов со стороны здесь нет вовсе.
"""
from __future__ import annotations

from html import escape

from aiohttp import web

from app import runtime

#: Что показываем в примерах, пока владелец не задал публичный адрес.
FALLBACK = "https://ваш-адрес"


def base() -> str:
    from app.api import server

    return server.base_url() or (FALLBACK + server.PREFIX)


ENDPOINTS = [
    ("GET", "/products", "Список товаров",
     "Необязательный ?type=stars|premium|steam|game"),
    ("GET", "/products/{id}", "Один товар", "id — из списка товаров"),
    ("GET", "/balance", "Остаток на балансе", ""),
    ("GET", "/user", "Аккаунт, ключ, лимиты, вебхук", ""),
    ("GET", "/orders", "Список заказов", "?limit=20&offset=0"),
    ("GET", "/orders/{order_id}", "Один заказ", "order_id — ORD-000123"),
    ("POST", "/order/create", "Создать заказ", "product_id, quantity, customer"),
    ("GET", "/order/status", "Статус заказа", "?order_id=ORD-000123"),
]

ERRORS = [
    ("400", "bad_json, bad_quantity, missing_customer", "Запрос не разобрать."),
    ("401", "invalid_key", "Ключ не принят."),
    ("402", "insufficient_funds", "Не хватает денег на балансе."),
    ("403", "key_disabled, account_blocked", "Ключ выключен или доступ закрыт."),
    ("404", "product_not_found, order_not_found", "Нет такого товара или заказа."),
    ("409", "in_progress", "Тот же idempotency_key ещё выполняется."),
    ("429", "rate_limited, too_many_attempts",
     "Слишком часто. В заголовке Retry-After — через сколько секунд повторить."),
    ("503", "api_disabled", "API временно выключен владельцем."),
]

STATUSES = [
    ("pending", "Заказ принят, ещё не в работе."),
    ("processing", "Отправлен поставщику, идёт выдача."),
    ("completed", "Выполнен."),
    ("failed", "Не выполнен, деньги не списаны или возвращены."),
    ("cancelled", "Отменён."),
    ("refunded", "Деньги вернулись на баланс."),
]

CSS = """
:root{--bg:#fff;--fg:#11161d;--muted:#5b6673;--line:#e4e8ee;--card:#f7f9fb;
--accent:#1f6feb;--code:#0d1117;--codefg:#e6edf3;--get:#1a7f37;--post:#9a3412}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;
--muted:#9198a1;--line:#242b33;--card:#161b22;--accent:#58a6ff;
--code:#010409;--codefg:#e6edf3;--get:#3fb950;--post:#f0883e}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:32px 20px 80px}
h1{font-size:30px;margin:0 0 6px;letter-spacing:-.4px}
h2{font-size:21px;margin:44px 0 12px;padding-top:20px;border-top:1px solid var(--line)}
h3{font-size:16px;margin:26px 0 8px}
p,li{color:var(--fg)}
.lead{color:var(--muted);margin:0 0 28px;font-size:17px}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13.5px}
p code,li code,td code{background:var(--card);border:1px solid var(--line);
border-radius:5px;padding:1px 5px}
pre{background:var(--code);color:var(--codefg);padding:16px 18px;border-radius:10px;
overflow-x:auto;font-size:13.5px;line-height:1.55}
pre code{background:none;border:0;padding:0;color:inherit}
table{width:100%;border-collapse:collapse;margin:14px 0;font-size:14.5px;
display:block;overflow-x:auto}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);
vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:13px;text-transform:uppercase;
letter-spacing:.4px}
.m{font-family:ui-monospace,monospace;font-weight:700;font-size:12.5px}
.get{color:var(--get)}.post{color:var(--post)}
.note{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent);
border-radius:0 8px 8px 0;padding:13px 16px;margin:18px 0;font-size:15px}
.tabs{display:flex;gap:4px;flex-wrap:wrap;margin:16px 0 0}
.tabs button{font:600 13px/1 inherit;padding:8px 14px;border:1px solid var(--line);
background:var(--card);color:var(--muted);border-radius:8px 8px 0 0;cursor:pointer}
.tabs button[aria-selected=true]{background:var(--code);color:var(--codefg);
border-color:var(--code)}
.tabs+pre{border-radius:0 10px 10px 10px;margin-top:0}
footer{margin-top:56px;padding-top:20px;border-top:1px solid var(--line);
color:var(--muted);font-size:14px}
"""

JS = """
document.querySelectorAll('.sample').forEach(function(box){
  var tabs = box.querySelectorAll('.tabs button');
  var panes = box.querySelectorAll('pre');
  tabs.forEach(function(tab, i){
    tab.addEventListener('click', function(){
      tabs.forEach(function(t,j){ t.setAttribute('aria-selected', j===i); });
      panes.forEach(function(p,j){ p.hidden = j!==i; });
    });
  });
});
"""


def _samples(url: str) -> str:
    """Один и тот же запрос на четырёх языках — чтобы просто скопировать."""
    curl = f"""curl -X POST {url}/order/create \\\\
  -H "Authorization: Bearer ВАШ_КЛЮЧ" \\\\
  -H "Content-Type: application/json" \\\\
  -H "Idempotency-Key: my-order-1001" \\\\
  -d '{{"product_id":"stars","quantity":100,"customer":"@durov"}}'"""

    php = f"""<?php
$ch = curl_init('{url}/order/create');
curl_setopt_array($ch, [
    CURLOPT_POST           => true,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_HTTPHEADER     => [
        'Authorization: Bearer ' . getenv('SHOP_API_KEY'),
        'Content-Type: application/json',
        'Idempotency-Key: my-order-1001',
    ],
    CURLOPT_POSTFIELDS => json_encode([
        'product_id' => 'stars',
        'quantity'   => 100,
        'customer'   => '@durov',
    ]),
]);
$answer = json_decode(curl_exec($ch), true);
curl_close($ch);

if (empty($answer['success'])) {{
    throw new RuntimeException($answer['error']['message'] ?? 'unknown');
}}
echo $answer['order_id'];   // ORD-000123"""

    python = f"""import os, requests

answer = requests.post(
    "{url}/order/create",
    headers={{
        "Authorization": f"Bearer {{os.environ['SHOP_API_KEY']}}",
        "Idempotency-Key": "my-order-1001",
    }},
    json={{"product_id": "stars", "quantity": 100, "customer": "@durov"}},
    timeout=30,
).json()

if not answer["success"]:
    raise RuntimeError(answer["error"]["message"])
print(answer["order_id"])   # ORD-000123"""

    js = f"""const answer = await fetch("{url}/order/create", {{
  method: "POST",
  headers: {{
    "Authorization": `Bearer ${{process.env.SHOP_API_KEY}}`,
    "Content-Type": "application/json",
    "Idempotency-Key": "my-order-1001",
  }},
  body: JSON.stringify({{
    product_id: "stars",
    quantity: 100,
    customer: "@durov",
  }}),
}}).then((r) => r.json());

if (!answer.success) throw new Error(answer.error.message);
console.log(answer.order_id);   // ORD-000123"""

    names = ["cURL", "PHP", "Python", "JavaScript"]
    blocks = [curl, php, python, js]
    tabs = "".join(
        f'<button aria-selected="{"true" if i == 0 else "false"}">{name}</button>'
        for i, name in enumerate(names)
    )
    panes = "".join(
        f'<pre{"" if i == 0 else " hidden"}><code>{escape(code)}</code></pre>'
        for i, code in enumerate(blocks)
    )
    return f'<div class="sample"><div class="tabs">{tabs}</div>{panes}</div>'


def _hook_sample() -> str:
    check = """# Python — проверка подписи вебхука
import hmac, hashlib

def genuine(body: bytes, header: str, secret: str) -> bool:
    mine = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mine, header)   # сравнение постоянное по времени"""
    return f"<pre><code>{escape(check)}</code></pre>"


def html() -> str:
    url = base()
    rows = "".join(
        f'<tr><td class="m {method.lower()}">{method}</td>'
        f"<td><code>{escape(path)}</code></td><td>{escape(what)}</td>"
        f"<td>{escape(note)}</td></tr>"
        for method, path, what, note in ENDPOINTS
    )
    errors = "".join(
        f"<tr><td class='m'>{code}</td><td><code>{escape(names)}</code></td>"
        f"<td>{escape(what)}</td></tr>"
        for code, names, what in ERRORS
    )
    statuses = "".join(
        f"<tr><td><code>{name}</code></td><td>{escape(what)}</td></tr>"
        for name, what in STATUSES
    )
    limit = runtime.get_int("api_rate_per_min", 60)

    order_answer = """{
  "success": true,
  "order_id": "ORD-000123",
  "status": "processing",
  "product_id": "stars",
  "quantity": 100,
  "amount": 1931,
  "amount_text": "19.31",
  "currency": "TJS",
  "customer": "@durov",
  "transaction_id": "TX-9F2A71B4C8D0",
  "created_at": "2026-09-15T10:04:11+00:00"
}"""
    status_answer = """{
  "success": true,
  "order_id": "ORD-000123",
  "status": "completed",
  "result": "@durov",
  "amount": 1931,
  "amount_text": "19.31",
  "currency": "TJS"
}"""
    error_answer = """{
  "success": false,
  "error": {
    "code": "insufficient_funds",
    "message": "Недостаточно средств.",
    "required": 1931,
    "balance": 400,
    "currency": "TJS"
  }
}"""
    hook_body = """{
  "event": "order.completed",
  "order_id": "ORD-000123",
  "status": "completed",
  "product_id": "stars",
  "quantity": 100,
  "amount": 1931,
  "customer": "@durov",
  "result": "@durov"
}"""

    return f"""<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>API — документация</title>
<style>{CSS}</style>
</head><body><div class="wrap">

<h1>API</h1>
<p class="lead">Покупка звёзд Telegram, Premium, Steam и игровых пакетов
из вашего кода — сайта, бота или приложения.</p>

<div class="note"><b>Базовый адрес:</b> <code>{escape(url)}</code><br>
Все запросы — по HTTPS. Ответ всегда JSON с полем <code>success</code>.</div>

<h2>Как начать</h2>
<ol>
<li>Напишите владельцу боту <code>/api</code> и создайте ключ.</li>
<li>Скопируйте ключ — он показывается <b>один раз</b>.</li>
<li>Пополните баланс — с него списываются покупки.</li>
<li>Передавайте ключ в каждом запросе:
<code>Authorization: Bearer ВАШ_КЛЮЧ</code></li>
</ol>

<div class="note">Ключ — это доступ к вашим деньгам. Держите его в
переменной окружения, не кладите в git и не показывайте в браузере:
запрос из JavaScript на странице отдаёт ключ каждому посетителю.
Вызывайте API со своего сервера.</div>

<h2>Точки</h2>
<table><thead><tr><th>Метод</th><th>Путь</th><th>Что делает</th>
<th>Параметры</th></tr></thead><tbody>{rows}</tbody></table>

<h2>Создать заказ</h2>
{_samples(url)}

<h3>Ответ</h3>
<pre><code>{escape(order_answer)}</code></pre>

<div class="note"><b>Деньги — целые числа</b> в дирамах
(1 сомони = 100 дирам). <code>amount: 1931</code> — это 19.31 сомони.
Так сделано нарочно: дробные числа при сложении дают копеечные
расхождения в любом языке.</div>

<h3>Повторный запрос</h3>
<p>Передайте <code>Idempotency-Key</code> (заголовком или полем
<code>idempotency_key</code>). Если тот же запрос уйдёт дважды —
из-за обрыва связи или повтора очереди, — второй раз деньги
<b>не спишутся</b>: вернётся тот же заказ.</p>

<h2>Статус заказа</h2>
<pre><code>curl "{escape(url)}/order/status?order_id=ORD-000123" \\
  -H "Authorization: Bearer ВАШ_КЛЮЧ"</code></pre>
<pre><code>{escape(status_answer)}</code></pre>

<table><thead><tr><th>Статус</th><th>Что значит</th></tr></thead>
<tbody>{statuses}</tbody></table>

<h2>Вебхук</h2>
<p>Укажите свой адрес в боте (<code>/api</code> → Вебхук) — и мы сами
сообщим, когда статус заказа изменится. Опрашивать
<code>/order/status</code> в цикле тогда не нужно.</p>
<pre><code>POST ваш-адрес
X-Signature: 3b099d0edd…
X-Signature-Algorithm: hmac-sha256

{escape(hook_body)}</code></pre>

<h3>Проверьте подпись</h3>
<p>Подпись — HMAC-SHA256 от <b>сырого тела</b> запроса на вашем секрете
<code>whsec_…</code>. Без проверки любой, кто узнает ваш адрес, сможет
прислать «заказ выполнен».</p>
{_hook_sample()}

<div class="note">Отвечайте <code>200</code>, как только приняли событие.
Если ответа нет, мы повторим — до 8 раз. Адрес должен быть
<code>https://</code> и вести наружу: внутренние адреса
(<code>127.0.0.1</code>, <code>10.x</code>) мы не вызываем.</div>

<h2>Ошибки</h2>
<pre><code>{escape(error_answer)}</code></pre>
<table><thead><tr><th>Код</th><th>error.code</th><th>Что значит</th></tr>
</thead><tbody>{errors}</tbody></table>

<h2>Лимиты</h2>
<ul>
<li><b>{limit} запросов в минуту</b> на ключ. Сверх — <code>429</code>
и заголовок <code>Retry-After</code>.</li>
<li>Короткий всплеск проходит целиком: лимит считается «дырявым ведром»,
а не жёстко по минутам.</li>
<li>Десять неверных ключей подряд с одного адреса закрывают его
на 5 минут.</li>
<li>В каждом ответе есть <code>X-Request-Id</code>. Если что-то не
работает — пришлите этот номер владельцу, по нему запрос найдётся
в журнале.</li>
</ul>

<footer>Вопросы — владельцу бота. Ключ в переписке не присылайте:
если он утёк, отзовите его в <code>/api</code> и создайте новый.</footer>

</div><script>{JS}</script></body></html>"""


async def page(request: web.Request) -> web.Response:
    return web.Response(text=html(), content_type="text/html", charset="utf-8")
