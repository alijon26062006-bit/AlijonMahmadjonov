"""Сайт: главная, регистрация/вход, документация и кабинет клиента."""

from __future__ import annotations

import json
import sqlite3
import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response

from . import accounts, cache, catalog, db, orders
from .config import PAY_METHODS, Config
from .deps import INDEXABLE, LoginRequired, check_csrf, flash, get_config, get_conn, render, session_user
from .money import apply_markup, fmt, order_total_micro, to_decimal
from .suppliers import KINDS, region_title

router = APIRouter(include_in_schema=False)


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def panel_user(request: Request, conn: sqlite3.Connection = Depends(get_conn)) -> sqlite3.Row:
    user = session_user(request, conn)
    if user is None:
        raise LoginRequired()
    return user


# ── Публичные страницы ───────────────────────────────────────


@router.get("/")
def home(request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    def build():
        cats = [dict(c) for c in catalog.categories(conn)]
        by_kind: dict[str, list] = {}
        for c in cats:
            by_kind.setdefault(c["kind"], []).append(c)
        return by_kind, sum(c["n"] for c in cats), _price_examples(conn, config)

    by_kind, total, examples = cache.get_or_set("home", 120, build)
    return render(request, "home.html", {
        "user": session_user(request, conn),
        "by_kind": by_kind,
        "total_products": total,
        "markups": config.markups,
        "examples": examples,
        "faq": FAQ,
    })


FAQ = [
    ("Что если заказ не выполнится?", "Деньги сразу вернутся на баланс."),
    ("Нужен ли программист?", "Нет, заказывать можно вручную в панели."),
    ("Как быстро выполняются заказы?", "Обычно за несколько секунд."),
]


def _price_examples(conn, config: Config) -> list[tuple[str, str]]:
    """Несколько реальных цен из каталога для главной (по базовой наценке)."""
    rows = []
    for pid, qty, label in (("tg-stars", 1000, "Telegram Stars, 1000 звёзд"),
                            ("tg-premium-3", 1, "Telegram Premium, 3 месяца"),
                            ("tg-premium-12", 1, "Telegram Premium, 12 месяцев")):
        p = catalog.get_product(conn, pid)
        if p is None:
            continue
        markup = config.kind_markups.get(p["kind"], config.markups["bronze"])
        total = order_total_micro(apply_markup(to_decimal(p["base_price"]), markup), qty)
        rows.append((label, fmt(total)))
    for c in catalog.categories(conn):
        if c["kind"] == "topup" and len(rows) < 5:
            items = catalog.list_products(conn, category_id=c["category_id"], limit=1)
            if items:
                p = items[0]
                total = order_total_micro(apply_markup(to_decimal(p["base_price"]), config.markups["bronze"]), 1)
                rows.append((f"{p['category_name']} — {p['name']}", fmt(total)))
    return rows


@router.get("/robots.txt")
def robots(config: Config = Depends(get_config)):
    body = ("User-agent: *\n"
            "Allow: /$\nAllow: /docs\nAllow: /register\nAllow: /static/\nAllow: /media/\n"
            "Disallow: /panel\nDisallow: /admin\nDisallow: /api/\nDisallow: /login\n\n"
            f"Sitemap: {config.base_url}/sitemap.xml\n")
    return PlainTextResponse(body)


@router.get("/sitemap.xml")
def sitemap(conn=Depends(get_conn), config: Config = Depends(get_config)):
    from xml.sax.saxutils import escape

    synced = (db.get_setting(conn, "catalog_synced_at") or db.now())[:10]
    urls = "".join(
        f"<url><loc>{escape(config.base_url + path)}</loc><lastmod>{synced}</lastmod>"
        f"<changefreq>{freq}</changefreq><priority>{prio}</priority></url>"
        for path, (freq, prio) in INDEXABLE.items()
    )
    return Response('<?xml version="1.0" encoding="UTF-8"?>\n'
                    f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
                    media_type="application/xml")


@router.get("/docs")
def docs(request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    return render(request, "docs.html", {"user": session_user(request, conn), "base_url": config.base_url})


@router.get("/register")
def register_form(request: Request, conn=Depends(get_conn)):
    if session_user(request, conn):
        return _redirect("/panel")
    return render(request, "register.html", {"form": {}})


@router.post("/register", dependencies=[Depends(check_csrf)])
def register(
    request: Request,
    email: str = Form(""),
    login: str = Form(""),
    password: str = Form(""),
    password2: str = Form(""),
    project: str = Form(""),
    conn=Depends(get_conn),
    config: Config = Depends(get_config),
):
    form = {"email": email, "login": login, "project": project}
    wait = request.app.state.limiter.hit("login", _ip(request))
    if wait is not None:
        return render(request, "register.html", {"form": form, "error": "Слишком много попыток. Подождите."}, 429)
    if password != password2:
        return render(request, "register.html", {"form": form, "error": "Пароли не совпадают."}, 400)
    try:
        user_id = accounts.create_user(
            conn, email=email, login=login, password=password, project=project,
            status="pending" if config.require_approval else "active",
        )
    except accounts.AccountError as exc:
        return render(request, "register.html", {"form": form, "error": str(exc)}, 400)
    request.session["user_id"] = user_id
    _record_login(conn, request, user_id)
    from .tgbot import user_event
    from .worker import notify_event
    if config.require_approval:
        notify_event(conn, config, user_event(conn, user_id))
        flash(request, "Аккаунт создан. Мы проверим заявку и активируем доступ — обычно в течение дня.")
    else:
        flash(request, "Аккаунт создан. Добро пожаловать!")
    return _redirect("/panel")


@router.get("/login")
def login_form(request: Request, conn=Depends(get_conn)):
    if session_user(request, conn):
        return _redirect("/panel")
    return render(request, "login.html", {"form": {}})


@router.post("/login", dependencies=[Depends(check_csrf)])
def login(request: Request, email: str = Form(""), password: str = Form(""), conn=Depends(get_conn)):
    wait = request.app.state.limiter.hit("login", _ip(request))
    if wait is not None:
        return render(request, "login.html", {"form": {"email": email},
                                              "error": "Слишком много попыток входа. Подождите 15 минут."}, 429)
    user = accounts.authenticate(conn, email, password)
    if user is None:
        return render(request, "login.html", {"form": {"email": email}, "error": "Неверный email или пароль."}, 400)
    if user["status"] == "blocked":
        return render(request, "login.html", {"form": {"email": email}, "error": "Аккаунт заблокирован."}, 403)
    request.session.clear()
    request.session["user_id"] = user["id"]
    _record_login(conn, request, user["id"])
    return _redirect("/admin" if user["role"] == "admin" else "/panel")


def _record_login(conn, request: Request, user_id: int) -> None:
    conn.execute("INSERT INTO logins (user_id, ip, user_agent, created_at) VALUES (?, ?, ?, ?)",
                 (user_id, _ip(request)[:64], request.headers.get("user-agent", "")[:300], db.now()))


@router.post("/logout", dependencies=[Depends(check_csrf)])
def logout(request: Request):
    request.session.clear()
    return _redirect("/")


def _ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")


# ── Кабинет ──────────────────────────────────────────────────


@router.get("/panel")
def panel_home(request: Request, user=Depends(panel_user), conn=Depends(get_conn),
               config: Config = Depends(get_config)):
    summary = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(total_micro), 0) AS spent FROM orders "
        "WHERE user_id = ? AND status = 'completed'",
        (user["id"],),
    ).fetchone()
    key = conn.execute(
        "SELECT id, prefix, created_at, last_used_at, key_enc IS NOT NULL AS can_show FROM api_keys "
        "WHERE user_id = ? AND revoked_at IS NULL "
        "ORDER BY id DESC LIMIT 1", (user["id"],)
    ).fetchone()
    return render(request, "panel/home.html", {
        "user": user, "summary": summary, "key": key, "kinds": KINDS,
        "markup": accounts.markup_for(user, config),
    })


@router.get("/panel/stats")
def panel_stats(request: Request, period: str = "30d", user=Depends(panel_user), conn=Depends(get_conn),
                config: Config = Depends(get_config)):
    from . import analytics
    return render(request, "panel/stats.html", {
        "user": user, "a": analytics.build(conn, period, user_id=user["id"], tz_hours=config.tz_offset),
    })


@router.get("/panel/logins")
def panel_logins(request: Request, user=Depends(panel_user), conn=Depends(get_conn)):
    rows = conn.execute("SELECT * FROM logins WHERE user_id = ? ORDER BY id DESC LIMIT 30", (user["id"],)).fetchall()
    return render(request, "panel/logins.html", {"user": user, "rows": rows})


def _cents(value) -> str:
    """Цена «от» для витрины: до центов, вверх — чтобы не обещать меньше реальной."""
    from decimal import ROUND_CEILING, Decimal

    return str(value.quantize(Decimal("0.01"), rounding=ROUND_CEILING))


# Разделы, где товары сгруппированы по играм/сервисам: сначала выбирают игру, потом пакет
_BY_GAME = ("topup", "gift_card", "game_key")


def _cached(key: str, q: str, make):
    """Каталог без поиска меняется только при загрузке — держим его минуту в памяти."""
    return make() if q else cache.get_or_set(key, 60, make)


@router.get("/panel/catalog")
def panel_catalog(
    request: Request, kind: str = "", q: str = "", category: str = "", region: str = "",
    user=Depends(panel_user), conn=Depends(get_conn), config: Config = Depends(get_config),
):
    kind = kind if kind in KINDS else ""
    q = q[:100]
    if kind in _BY_GAME and not category:
        # Цена «от» — уже с наценкой клиента, закупочную не показываем
        games = [
            {**dict(c), "regions": sorted(filter(None, (c["regions"] or "").split(","))),
             "from_price": _cents(apply_markup(to_decimal(str(c["from_price"])),
                                               accounts.markup_for(user, config, c["kind"])))}
            for c in _cached(f"cats:{kind}", q, lambda: [dict(c) for c in catalog.categories(conn, kind=kind, q=q)])
        ]
        return render(request, "panel/catalog.html", {
            "user": user, "games": games, "kind": kind, "q": q, "kinds": KINDS, "count": len(games),
            "region_title": region_title,
        })
    products = _cached(f"products:{kind}:{category}", q,
                       lambda: catalog.list_products(conn, kind=kind, q=q, category_id=category))
    regions = sorted({p["region"] for p in products if p.get("region")})
    game = products[0] if category and products else None
    if region:
        products = [p for p in products if p.get("region") == region]
    items = [catalog.public_view(p, accounts.markup_for(user, config, p["kind"])) for p in products]
    groups: dict[str, list] = {}
    for item in items:
        groups.setdefault(f"{item['kind_title']} · {item['category_name']}", []).append(item)
    return render(request, "panel/catalog.html", {
        "user": user, "groups": groups, "kind": kind, "q": q, "kinds": KINDS, "count": len(items),
        "category": category, "game": game, "regions": regions, "region": region, "region_title": region_title,
    })


@router.get("/panel/buy/{product_id}")
def panel_buy_form(product_id: str, request: Request, user=Depends(panel_user), conn=Depends(get_conn),
                   config: Config = Depends(get_config)):
    p = catalog.get_product(conn, product_id)
    if p is None:
        flash(request, "Товар недоступен.", "error")
        return _redirect("/panel/catalog")
    form = {k[6:]: v[:100] for k, v in request.query_params.items() if k.startswith("field_")}
    return render(request, "panel/buy.html", _buy_ctx(request, conn, config, user, p, form=form))


def _buy_ctx(request: Request, conn, config: Config, user, p: dict, **extra) -> dict:
    """Всё для страницы покупки: товар, другие пакеты этой игры, можно ли проверить аккаунт."""
    from . import account_check
    markup = accounts.markup_for(user, config, p["kind"])
    siblings = []
    if p["kind"] in _BY_GAME:
        siblings = [catalog.public_view(s, markup) for s in
                    catalog.list_products(conn, kind=p["kind"], category_id=p["category_id"], limit=200)]
    return {
        "user": user, "p": catalog.public_view(p, markup), "siblings": siblings, "idem": str(uuid.uuid4()),
        "can_check": account_check.can_check(request.app.state.supplier, p), "form": {}, **extra,
    }


async def _form(request: Request) -> dict[str, str]:
    return {k: str(v) for k, v in (await request.form()).items()}


@router.post("/panel/buy/{product_id}", dependencies=[Depends(check_csrf)])
def panel_buy(product_id: str, request: Request, form: dict = Depends(_form), user=Depends(panel_user),
              conn=Depends(get_conn), config: Config = Depends(get_config)):
    # Обычная (не async) функция: FastAPI выполнит её в отдельном потоке,
    # и ожидание ответа поставщика не остановит остальной сайт.
    p = catalog.get_product(conn, product_id)
    if p is None:
        flash(request, "Товар недоступен.", "error")
        return _redirect("/panel/catalog")
    fields = {f["key"]: str(form.get(f"field_{f['key']}", "")) for f in p["fields"]}
    try:
        order, _ = orders.create_order(
            conn, config, request.app.state.supplier, user,
            product_id=product_id, quantity=form.get("quantity", 1), fields=fields,
            client_idem_key="panel-" + str(form.get("idem", ""))[:64], source="panel",
        )
    except orders.OrderError as exc:
        return render(request, "panel/buy.html", _buy_ctx(
            request, conn, config, accounts.get_user(conn, user["id"]), p, error=str(exc),
            form={**fields, "quantity": form.get("quantity", "")}), 400)
    return _redirect(f"/panel/orders/{order['public_id']}")


@router.get("/panel/data/check-account/{product_id}")
def panel_check_account(product_id: str, request: Request, user=Depends(panel_user), conn=Depends(get_conn)):
    from .api import ApiError, account_check_view
    p = catalog.get_product(conn, product_id)
    if p is None:
        return JSONResponse({"ok": False, "error": "Товар не найден."}, 404)
    if request.app.state.limiter.hit("status", f"web{user['id']}") is not None:
        return JSONResponse({"ok": False, "error": "Слишком часто. Подождите минуту."}, 429)
    fields = {k[6:]: v for k, v in request.query_params.items() if k.startswith("field_")}
    try:
        return {"ok": True, **account_check_view(request.app.state.supplier, p, fields)}
    except ApiError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, exc.http_status)


@router.get("/panel/data/gamekey-regions/{product_id}")
def panel_gamekey_regions(product_id: str, request: Request, user=Depends(panel_user), conn=Depends(get_conn)):
    from . import gamekeys
    p = catalog.get_product(conn, product_id)
    if p is None or p["kind"] != "game_key":
        return JSONResponse({"ok": False, "error": "Товар не найден."}, 404)
    return {"ok": True, **gamekeys.regions(request.app.state.supplier, p["supplier_ref"]["game_id"])}


@router.get("/panel/data/steam-gifts/games")
def panel_gift_games(q: str = "", user=Depends(panel_user), conn=Depends(get_conn)):
    from . import steam_gifts
    return {"ok": True, "items": steam_gifts.search(conn, q[:100])}


@router.get("/panel/data/steam-gifts/games/{appid}")
def panel_gift_game(appid: int, request: Request, user=Depends(panel_user), conn=Depends(get_conn),
                    config: Config = Depends(get_config)):
    from .api import ApiError, steam_gift_view
    try:
        return steam_gift_view(request, conn, config, user, appid)
    except ApiError as exc:
        return JSONResponse({"ok": False, "error": str(exc), "code": exc.code}, status_code=exc.http_status)


@router.get("/panel/orders")
def panel_orders(request: Request, status: str = "", q: str = "", page: int = 1,
                 user=Depends(panel_user), conn=Depends(get_conn)):
    per = 30
    page = max(page, 1)
    where, args = "user_id = ?", [user["id"]]
    if status == "processing":
        where += " AND status IN ('processing', 'attention')"
    elif status in ("completed", "failed"):
        where += " AND status = ?"
        args.append(status)
    if q:
        where += " AND (public_id LIKE ? OR product_name LIKE ? OR fields_json LIKE ?)"
        args += [f"%{q}%"] * 3
    total = conn.execute(f"SELECT COUNT(*) FROM orders WHERE {where}", args).fetchone()[0]
    rows = conn.execute(f"SELECT * FROM orders WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                        [*args, per, (page - 1) * per]).fetchall()
    return render(request, "panel/orders.html", {
        "user": user, "orders": rows, "status": status, "q": q, "page": page,
        "pages": max(1, -(-total // per)), "total": total,
    })


@router.get("/panel/orders/{public_id}")
def panel_order(public_id: str, request: Request, user=Depends(panel_user), conn=Depends(get_conn)):
    row = orders.find_user_order(conn, user["id"], public_id)
    if row is None:
        flash(request, "Заказ не найден.", "error")
        return _redirect("/panel/orders")
    row = orders.refresh_if_stale(conn, request.app.state.supplier, row)
    return render(request, "panel/order.html", {
        "user": user, "o": row, "view": orders.public_view(row),
        "delivery_pretty": json.dumps(orders.public_view(row)["delivery"], ensure_ascii=False, indent=2),
    })


@router.get("/panel/transactions")
def panel_transactions(request: Request, type: str = "", page: int = 1,
                       user=Depends(panel_user), conn=Depends(get_conn)):
    per = 40
    page = max(page, 1)
    where, args = "t.user_id = ?", [user["id"]]
    if type in ("credit", "debit"):
        where += " AND t.type = ?"
        args.append(type)
    total = conn.execute(f"SELECT COUNT(*) FROM transactions t WHERE {where}", args).fetchone()[0]
    rows = conn.execute(
        f"SELECT t.*, o.public_id AS order_public FROM transactions t LEFT JOIN orders o ON o.id = t.order_id "
        f"WHERE {where} ORDER BY t.id DESC LIMIT ? OFFSET ?", [*args, per, (page - 1) * per]
    ).fetchall()
    return render(request, "panel/transactions.html", {
        "user": user, "rows": rows, "type": type, "page": page, "pages": max(1, -(-total // per)),
    })


@router.get("/panel/balance")
def panel_balance(request: Request, user=Depends(panel_user), conn=Depends(get_conn),
                  config: Config = Depends(get_config)):
    from . import payments, rates
    rates.refresh(conn, config, rates.PAYMENT_SECONDS)
    rows = conn.execute("SELECT * FROM payments WHERE user_id = ? ORDER BY id DESC LIMIT 20", (user["id"],)).fetchall()
    conf = payments.settings(conn, config)
    return render(request, "panel/balance.html", {
        "user": user, "methods": payments.methods(conn, config), "payments": rows, "tjs_rate": conf["tjs_rate"],
        "min_usd": conf["min_usd"], "min_tjs": conf["min_tjs"],
        "pay_titles": {k: v[0] for k, v in PAY_METHODS.items()} | {m["code"]: m["title"] for m in conf["all_methods"]},
    })


# ── Свой Telegram-бот (конструктор) ──────────────────────────


@router.get("/panel/bots")
def panel_bots(request: Request, user=Depends(panel_user), conn=Depends(get_conn)):
    from . import bots
    return render(request, "panel/bots.html", {
        "user": user, "bots": bots.listing(conn, user["id"]), "max_bots": bots.MAX_PER_CLIENT,
        "ready": bots.RUNNER is not None and bots.TEMPLATE_DIR.exists(),
    })


@router.post("/panel/bots", dependencies=[Depends(check_csrf)])
def panel_bots_add(request: Request, token: str = Form(""), admin_ids: str = Form(""),
                   user=Depends(panel_user), conn=Depends(get_conn), config: Config = Depends(get_config)):
    from . import bots
    from .worker import notify_admin
    if user["status"] != "active":
        flash(request, "Бот можно подключить после подтверждения аккаунта.", "error")
        return _redirect("/panel/bots")
    have = conn.execute("SELECT COUNT(*) FROM bots WHERE user_id = ?", (user["id"],)).fetchone()[0]
    if have >= bots.MAX_PER_CLIENT:
        flash(request, f"Можно подключить до {bots.MAX_PER_CLIENT} ботов. Удалите ненужного.", "error")
        return _redirect("/panel/bots")
    try:
        username = bots.check_token(token)
        bots.create(conn, config, user_id=user["id"], token=token, admin_ids=admin_ids, username=username)
    except bots.BotError as exc:
        flash(request, str(exc), "error")
        return _redirect("/panel/bots")
    if bots.RUNNER:
        bots.RUNNER.poke()
    notify_admin(config, f"🤖 Клиент {user['login']} подключил бота @{username} в конструкторе.")
    flash(request, f"Бот @{username} подключён — запустится в течение минуты. Откройте его и нажмите /start, "
                   "затем /panel — там игры, цены и реквизиты.")
    return _redirect("/panel/bots")


@router.post("/panel/bots/{bot_id}/{action}", dependencies=[Depends(check_csrf)])
def panel_bots_action(bot_id: int, action: str, request: Request, admin_ids: str = Form(""),
                      user=Depends(panel_user), conn=Depends(get_conn)):
    from . import bots
    if not bots.owned(conn, bot_id, user["id"]):
        flash(request, "Бот не найден.", "error")
        return _redirect("/panel/bots")
    try:
        if action == "stop":
            bots.set_enabled(conn, bot_id, False)
        elif action in ("start", "restart"):
            bots.set_enabled(conn, bot_id, True)  # updated_at меняется — процесс перезапустится
        elif action == "admins":
            bots.update_admins(conn, bot_id, admin_ids)
            flash(request, "Админы бота обновлены.")
        elif action == "delete":
            bots.delete(conn, bot_id)
            flash(request, "Бот удалён, его API-ключ отозван.")
    except bots.BotError as exc:
        flash(request, str(exc), "error")
    if bots.RUNNER:
        bots.RUNNER.poke()
    return _redirect("/panel/bots")


@router.get("/panel/data/rate")
def panel_rate(user=Depends(panel_user), conn=Depends(get_conn), config: Config = Depends(get_config)):
    """Страница оплаты спрашивает курс каждые 30 секунд."""
    from . import payments, rates
    rates.refresh(conn, config, rates.PAYMENT_SECONDS)
    conf = payments.settings(conn, config)
    st = rates.status(conn, config)
    return JSONResponse({"tjs_rate": str(conf["tjs_rate"]), "min_usd": str(conf["min_usd"]),
                         "auto": st["auto"], "age_seconds": st["age_seconds"]})


@router.post("/panel/balance", dependencies=[Depends(check_csrf)])
def panel_balance_request(request: Request, method: str = Form(""), amount: str = Form(""),
                          reference: str = Form(""), receipt: UploadFile | None = File(None),
                          user=Depends(panel_user), conn=Depends(get_conn),
                          config: Config = Depends(get_config)):
    from . import payments
    from .tgbot import payment_event, send_receipt
    from .worker import notify_event
    from . import rates
    data = receipt.file.read(payments.MAX_RECEIPT_BYTES + 1) if receipt and receipt.filename else b""
    rates.refresh(conn, config, rates.PAYMENT_SECONDS)  # сумма к переводу — по свежему курсу
    try:
        with db.tx(conn):
            pid = payments.create(conn, config, user, method, amount, reference)
            if data:
                payments.attach_receipt(conn, config, user["id"], pid, data, receipt.content_type or "")
    except payments.PaymentError as exc:
        flash(request, str(exc), "error")
        return _redirect("/panel/balance")
    row = conn.execute("SELECT * FROM payments WHERE id = ?", (pid,)).fetchone()
    if data:
        send_receipt(conn, config, pid)
    else:
        notify_event(conn, config, payment_event(conn, pid, config))
    flash(request, f"Заявка #{pid} создана. Переведите {row['pay_amount']} {row['pay_currency']} по реквизитам — "
                   "после проверки баланс пополнится, вам придёт уведомление.")
    return _redirect("/panel/balance")


@router.post("/panel/balance/{payment_id}/cancel", dependencies=[Depends(check_csrf)])
def panel_balance_cancel(payment_id: int, request: Request, user=Depends(panel_user), conn=Depends(get_conn)):
    from . import payments
    payments.cancel(conn, user["id"], payment_id)
    flash(request, "Заявка отменена.")
    return _redirect("/panel/balance")


@router.get("/panel/notifications")
def panel_notifications(request: Request, user=Depends(panel_user), conn=Depends(get_conn)):
    from . import notify
    rows = notify.latest(conn, user["id"])
    notify.mark_read(conn, user["id"])
    return render(request, "panel/notifications.html", {"user": user, "rows": rows})


@router.get("/panel/api")
def panel_api(request: Request, user=Depends(panel_user), conn=Depends(get_conn),
              config: Config = Depends(get_config)):
    keys = conn.execute(
        "SELECT * FROM api_keys WHERE user_id = ? ORDER BY revoked_at IS NOT NULL, id DESC", (user["id"],)
    ).fetchall()
    new_key = request.session.pop("new_api_key", None)
    return render(request, "panel/api.html", {
        "user": user, "keys": keys, "new_key": new_key, "base_url": config.base_url,
    })


@router.post("/panel/api/keys", dependencies=[Depends(check_csrf)])
def panel_api_create(request: Request, name: str = Form(""), user=Depends(panel_user), conn=Depends(get_conn)):
    try:
        key = accounts.create_api_key(conn, user["id"], name, request.app.state.config.secret_key)
    except accounts.AccountError as exc:
        flash(request, str(exc), "error")
        return _redirect("/panel/api")
    request.session["new_api_key"] = key
    return _redirect("/panel/api")


@router.post("/panel/api/keys/{key_id}/reveal", dependencies=[Depends(check_csrf)])
def panel_api_reveal(key_id: int, request: Request, user=Depends(panel_user), conn=Depends(get_conn)):
    if request.app.state.limiter.hit("account", f"reveal{user['id']}") is not None:
        return JSONResponse({"ok": False, "error": "Слишком часто. Подождите минуту."}, 429)
    key = accounts.reveal_api_key(conn, user["id"], key_id, request.app.state.config.secret_key)
    if key is None:
        return JSONResponse({"ok": False, "error": "Этот ключ создан до обновления — его нельзя показать. "
                                                  "Создайте новый в «Управление ключами»."}, 404)
    return JSONResponse({"ok": True, "key": key}, headers={"Cache-Control": "no-store"})


@router.post("/panel/api/keys/{key_id}/revoke", dependencies=[Depends(check_csrf)])
def panel_api_revoke(key_id: int, request: Request, user=Depends(panel_user), conn=Depends(get_conn)):
    accounts.revoke_api_key(conn, user["id"], key_id)
    flash(request, "Ключ отозван.")
    return _redirect("/panel/api")


@router.post("/panel/api/webhook", dependencies=[Depends(check_csrf)])
def panel_webhook(request: Request, webhook_url: str = Form(""), rotate: str = Form(""),
                  user=Depends(panel_user), conn=Depends(get_conn)):
    try:
        accounts.set_webhook(conn, user["id"], webhook_url)
        if rotate:
            accounts.rotate_webhook_secret(conn, user["id"])
    except accounts.AccountError as exc:
        flash(request, str(exc), "error")
        return _redirect("/panel/api")
    flash(request, "Настройки webhook сохранены.")
    return _redirect("/panel/api")

