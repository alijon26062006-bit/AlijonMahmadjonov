"""Мини-приложение Telegram /tg: Stars, Premium, Подарки — одна страница, пять вкладок.

Кто открыл — по подписи Telegram (initData, подписана токеном бота мини-приложения). Аккаунт тот же,
что у бота-магазина: Telegram ID → аккаунт Donatix (общий баланс, заказы, рефералка).
Stars и Premium — обычные заказы каталога (source='tgapp'), подарки — tggifts.
"""

from __future__ import annotations

import re
import secrets
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from . import accounts, catalog, db, jumuah, orders, refs, tggifts, tgnotify
from .config import Config
from .deps import get_config, get_conn, templates
from .support_app import check_init

router = APIRouter(prefix="/tg", include_in_schema=False)
SOURCE = "tgapp"
STAR_PACKS = (50, 75, 100, 150, 250, 350, 500, 750, 1000)
# Куда мини-приложение пускает на сайт под аккаунтом Telegram (только эти страницы — без открытого редиректа)
SITE_PAGES = {"games": "/panel/catalog?kind=topup", "cards": "/panel/catalog?kind=gift_card", "orders": "/panel/orders"}
USERNAME_RE = re.compile(r"^@?[A-Za-z][A-Za-z0-9_]{3,31}$")


def _tg(request: Request, config: Config) -> dict[str, Any] | None:
    """Кто зовёт: мини-приложение (подпись Telegram) или приложение сайта /app (вход на сайте).

    Для входа на сайте нужен заголовок X-Dx-App с токеном формы этой сессии: чужой сайт его не знает и
    прислать не может, поэтому подделать запрос от имени клиента нельзя."""
    tg = check_init(request.headers.get("x-tg-init", ""), config.gift_bot_token)
    if tg:
        return tg
    token, expected = request.headers.get("x-dx-app", ""), request.session.get("csrf", "")
    if token and expected and secrets.compare_digest(token, expected) and request.session.get("user_id"):
        return {"id": 0, "site": True, "_req": request, "first_name": "", "language_code": "ru"}
    return None


def _deny() -> JSONResponse:
    return JSONResponse({"error": "Мағозаро аз Telegram-бот кушоед. / Откройте магазин из Telegram-бота."}, status_code=403)


def _account(conn, tg: dict[str, Any], start: str = ""):
    """Аккаунт Donatix этого Telegram (тот же, что в боте-магазине) или вошедший на сайте клиент."""
    if tg.get("site"):
        from fastapi import HTTPException

        from .deps import session_user
        user = session_user(tg["_req"], conn)
        if user is None or user["role"] == "admin":
            raise HTTPException(status_code=403, detail="Войдите в аккаунт.")
        return user
    from .shopbot import ensure_user
    su = ensure_user(conn, int(tg["id"]), tg.get("first_name") or "", start, username=tg.get("username") or "")
    tggifts.remember_user(conn, tg)
    if start.startswith("r_"):
        from . import referrals
        referrals.attach(conn, su["user_id"], start[2:])
    return accounts.get_user(conn, su["user_id"])


def _refund_needed(conn, user) -> bool:
    from . import refunds
    return bool(refunds.needed(conn, user))


def _watch(conn, kind: str, obj_id: int, tg: dict[str, Any]) -> None:
    if not tg.get("site"):        # клиенту сайта о заказе и оплате сообщают уведомления сайта
        tgnotify.add(conn, kind, obj_id, tg)


def _rate(conn, config: Config) -> str:
    from .payments import settings
    return str(settings(conn, config)["tjs_rate"])


def _stars(conn, config: Config, user) -> dict[str, Any] | None:
    from .money import apply_markup, to_decimal
    p = catalog.get_product(conn, "tg-stars")
    if p is None:
        return None
    unit = apply_markup(to_decimal(p["base_price"]), accounts.markup_for(user, config, p["kind"]))
    return {"product_id": p["id"], "unit_usd": str(unit), "min": max(50, p["min_qty"]), "max": p["max_qty"],
            "packs": [n for n in STAR_PACKS if p["min_qty"] <= n <= p["max_qty"]]}


def _premium(conn, config: Config, user) -> list[dict[str, Any]]:
    plans = []
    for p in catalog.list_products(conn, kind="telegram_premium"):
        v = catalog.public_view(p, accounts.markup_for(user, config, p["kind"]), config=config, user=user)
        m = re.search(r"(\d+)", p["name"])
        months = int(m.group(1)) if m else 0
        if months:
            plans.append({"product_id": p["id"], "months": months, "price_usd": v["price_usd"]})
    plans.sort(key=lambda x: x["months"])
    base = next((float(x["price_usd"]) / x["months"] for x in plans), 0)
    for x in plans:
        per = float(x["price_usd"]) / x["months"]
        x["save"] = round((1 - per / base) * 100) if base and per < base else 0
    return plans


def _feed(conn, lang: str = "tj") -> list[dict[str, Any]]:
    """Последние покупки всех: имя покупателя (только имя из Telegram), что купил, когда. Подписи — на языке открывшего."""
    tggifts.ensure(conn)
    rows = conn.execute(
        "SELECT * FROM ("
        " SELECT o.kind AS kind, o.quantity AS qty, o.product_name AS name, o.updated_at AS at, "
        "        COALESCE(su.name, '') AS who, NULL AS emoji FROM orders o "
        " LEFT JOIN shop_users su ON su.user_id = o.user_id "
        " WHERE o.status = 'completed' AND o.kind IN ('telegram_stars', 'telegram_premium') "
        " UNION ALL "
        " SELECT 'gift', g.star_count, '', g.updated_at, COALESCE(su.name, ''), t.emoji FROM gift_orders g "
        " LEFT JOIN shop_users su ON su.user_id = g.user_id LEFT JOIN tg_gifts t ON t.id = g.gift_id "
        " WHERE g.status = 'sent') ORDER BY at DESC LIMIT 12").fetchall()
    out = []
    for r in rows:
        who = (r["who"] or "").split()[0] if r["who"] else ""
        if r["kind"] == "telegram_stars":
            what = f"{r['qty']} Stars"
        elif r["kind"] == "telegram_premium":
            m = re.search(r"(\d+)", r["name"] or "")
            what = f"Premium · {m.group(1) if m else ''} {'мес' if lang == 'ru' else 'моҳ'}"
        else:
            what = f"{r['emoji'] or '🎁'} Gift · {r['qty']}⭐"
        out.append({"who": who or ("Покупатель" if lang == "ru" else "Харидор"), "what": what, "kind": r["kind"], "at": r["at"]})
    return out


def _stats(conn, user_id: int) -> dict[str, int]:
    tggifts.ensure(conn)
    o = conn.execute("SELECT COUNT(*) AS n, COALESCE(SUM(total_micro), 0) AS spent, "
                     "COALESCE(SUM(CASE WHEN kind = 'telegram_stars' THEN quantity END), 0) AS stars "
                     "FROM orders WHERE user_id = ? AND status = 'completed'", (user_id,)).fetchone()
    g = conn.execute("SELECT COUNT(*) AS n, COALESCE(SUM(price_micro), 0) AS spent FROM gift_orders "
                     "WHERE user_id = ? AND status IN ('sent', 'paid', 'sending', 'unknown', 'awaiting_recipient')",
                     (user_id,)).fetchone()
    topped = conn.execute("SELECT COALESCE(SUM(amount_micro), 0) FROM transactions WHERE user_id = ? "
                          "AND type = 'credit' AND order_id IS NULL AND note NOT LIKE 'Возврат%'",
                          (user_id,)).fetchone()[0]
    return {"orders": o["n"] + g["n"], "stars": int(o["stars"]), "spent": int(o["spent"] + g["spent"]),
            "topped": int(topped)}


@router.get("")
def page(request: Request, config: Config = Depends(get_config)):
    from . import banners, db
    pool = db.pool(config.db_path)
    conn = pool.acquire()
    try:
        ads = banners.active(conn)    # та же лента рекламы, что на сайте
    finally:
        pool.release(conn)
    return templates.TemplateResponse(request, "tg_app.html", {"site_name": config.site_name,
                                                               "support": config.support_contact, "banners": ads})


@router.get("/gift/{name}")
def gift_img(name: str, config: Config = Depends(get_config)):
    m = re.fullmatch(r"[A-Za-z0-9]{1,40}\.(webp|json|webm)", name)
    if not m:
        return Response(status_code=404)
    path = tggifts.img_dir(config) / name
    if not path.exists():
        return Response(status_code=404)
    kind = {"webp": "image/webp", "json": "application/json", "webm": "video/webm"}[m.group(1)]
    return FileResponse(path, media_type=kind, headers={"Cache-Control": "public, max-age=86400"})


@router.post("/api/init")
async def api_init(request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    tg = _tg(request, config)
    if not tg:
        return _deny()
    body = await request.json()
    user = _account(conn, tg, str(body.get("start") or "")[:64])
    from . import referrals
    bot = db.get_setting(conn, "gifts.bot_username") or ""
    return {
        "me": {"id": user["id"] if tg.get("site") else tg["id"], "name": tg.get("first_name") or user["login"] or "",
               "username": tg.get("username") or "",
               "photo": tg.get("photo_url") or "", "balance": user["balance_micro"]},
        "stats": _stats(conn, user["id"]),
        "rate": _rate(conn, config),
        "stars": _stars(conn, config, user),
        "premium": _premium(conn, config, user),
        "gifts": tggifts.listing(conn, config, user) if tggifts.enabled(config) and not tg.get("site") else [],
        "refund_needed": bool(tg.get("site")) and _refund_needed(conn, user),
        "feed": _feed(conn, tgnotify.lang_of(tg)),
        "ref": {"percent": referrals.percent(conn), "invited": referrals.stats(conn, user["id"])["invited"],
                "link": f"https://t.me/{bot}?start=r_{referrals.code_for(conn, user['id'])}" if bot else ""},
        "bot": bot,
        "friday": jumuah.MESSAGE if jumuah.closed(config) else "",
        "pay": _pay_info(request, conn, config, user),
        "reviews": _reviews_short(conn),
    }


# ── Каталог прямо в мини-приложении: игры, карты, Steam. На сайт не уходим ──

def _cover(kind: str, url: str | None) -> str:
    from .deps import _img, kind_cover
    return _img(kind_cover(kind, url)) if kind_cover(kind, url) else ""


def _tiles(conn, config: Config, user, kinds: tuple[str, ...]) -> list[dict[str, Any]]:
    from .money import apply_markup, to_decimal
    out = []
    for kind in kinds:
        for c in catalog.categories(conn, kind=kind):
            price = apply_markup(to_decimal(str(c["from_price"])), accounts.markup_for(user, config, c["kind"]))
            out.append({"kind": c["kind"], "category": c["category_id"], "name": c["category_name"], "n": c["n"],
                        "img": _cover(c["kind"], c["image_url"]), "from_usd": str(price),
                        "regions": sorted(filter(None, (c["regions"] or "").split(",")))})
    return out


@router.post("/api/catalog")
async def api_catalog(request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    tg = _tg(request, config)
    if not tg:
        return _deny()
    user = _account(conn, tg)
    from . import popular
    hot = []
    for p in popular.services(conn):
        if p.get("key") == "telegram":
            continue
        hot.append({"kind": p["kind"], "category": p.get("category_id") or "", "region": p.get("region") or "",
                    "name": p["title"], "img": _cover(p["kind"], p.get("image_url")), "hot": True})
    games = _tiles(conn, config, user, ("topup",))
    for g in games:      # FF СНГ / FF Инд — как на сайте, своими названиями и обложками
        same = next((h for h in hot if h["category"] == g["category"] and h["kind"] == g["kind"]), None)
        if same:
            g["name"], g["img"], g["hot"] = same["name"], same["img"] or g["img"], True
    games.sort(key=lambda g: (not g.get("hot"), g["name"].lower()))
    return {"games": games, "cards": _tiles(conn, config, user, ("gift_card", "game_key", "steam_topup")),
            "popular": [h for h in hot if h["category"]]}


@router.post("/api/game")
async def api_game(request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    tg = _tg(request, config)
    if not tg:
        return _deny()
    user = _account(conn, tg)
    body = await request.json()
    kind, category, region = str(body.get("kind") or "")[:32], str(body.get("category") or "")[:64], str(body.get("region") or "")[:16]
    products = [p for p in catalog.list_products(conn, kind=kind, category_id=category)
                if p["kind"] not in ("telegram_stars", "telegram_premium")]
    if not products:
        return JSONResponse({"error": "Мол дастрас нест. / Товар недоступен."}, status_code=404)
    regions = sorted({p["region"] for p in products if p.get("region")})
    if region:
        products = [p for p in products if p.get("region") == region] or products
    items = [catalog.public_view(p, accounts.markup_for(user, config, p["kind"]), config=config, user=user) for p in products]
    from . import packs
    from .suppliers import region_title
    if kind == "topup":
        items.sort(key=lambda i: packs.order_key(i["name"], float(i["price_usd"])))
    else:
        items.sort(key=lambda i: float(i["price_usd"]))
    for i in items:
        i["img"] = i.get("image_url") or ""
        i["group_title"] = (f"{packs.GROUP_EMOJI[i['group']]} {packs.GROUP_TITLES[i['group']]}" if i.get("group") is not None else "")
    first = products[0]
    return {"name": first["category_name"], "kind": first["kind"], "img": _cover(first["kind"], first.get("image_url")),
            "regions": [{"code": r, "title": region_title(r)} for r in regions], "region": region,
            "note": catalog.delivery_note(first["category_name"]), "items": items}


@router.post("/api/order")
async def api_order(request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    """Покупка любого товара каталога с баланса — прямо в мини-приложении."""
    tg = _tg(request, config)
    if not tg:
        return _deny()
    body = await request.json()
    user = _account(conn, tg)
    if jumuah.blocks(config, user, SOURCE):
        return {"ok": False, "error": jumuah.MESSAGE}
    p = catalog.get_product(conn, str(body.get("product_id") or ""))
    if p is None or p["kind"] in ("telegram_stars", "telegram_premium"):
        return {"ok": False, "error": "Мол дастрас нест. / Товар недоступен."}
    raw = body.get("fields") if isinstance(body.get("fields"), dict) else {}
    fields = {str(k)[:40]: str(v).strip()[:200] for k, v in raw.items()}
    qty = body.get("qty") or 1
    from . import quickbuy
    supplier = request.app.state.supplier
    try:
        order, _ = orders.create_order(conn, config, supplier, user, product_id=p["id"], quantity=qty, fields=fields,
                                       client_idem_key="tgapp-" + str(body.get("idem") or uuid.uuid4())[:64], source=SOURCE)
    except orders.OrderError as exc:
        if exc.code == "insufficient_balance":
            try:
                return _need(user, quickbuy.need_micro(config, supplier, user, p, qty, fields))
            except orders.OrderError as exc2:
                return {"ok": False, "error": str(exc2)}
        return {"ok": False, "error": str(exc)}
    _watch(conn, "order", order["id"], tg)
    return {"ok": True, "ref": order["public_id"], "balance": accounts.get_user(conn, user["id"])["balance_micro"],
            "message": f"✅ Фармоиш № {order['public_id']} қабул шуд. / Заказ № {order['public_id']} принят."}


@router.post("/api/order/view")
async def api_order_view(request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    tg = _tg(request, config)
    if not tg:
        return _deny()
    user = _account(conn, tg)
    body = await request.json()
    row = conn.execute("SELECT * FROM orders WHERE public_id = ? AND user_id = ?",
                       (str(body.get("ref") or "")[:40], user["id"])).fetchone()
    if row is None:
        return JSONResponse({"error": "Фармоиш ёфт нашуд. / Заказ не найден."}, status_code=404)
    v = orders.public_view(row)
    return {"ref": v["order_id"], "status": v["status"], "title": v["product_name"], "qty": v["quantity"],
            "fields": v["fields"], "total": row["total_micro"], "items": v["delivery_items"], "error": v["error"],
            "at": v["created_at"], "kind": v["kind"]}


def _reviews_short(conn) -> dict[str, Any]:
    from . import reviews
    try:
        s = reviews.summary(conn)
    except Exception:  # noqa: BLE001 — таблицы отзывов нет (старые базы в тестах)
        return {"total": 0, "avg": 0}
    return {"total": s["total"], "avg": s["avg"]}


@router.post("/api/reviews")
async def api_reviews(request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    tg = _tg(request, config)
    if not tg:
        return _deny()
    from . import reviews
    s = reviews.summary(conn)
    items = [{"name": r["name"], "initials": r["initials"], "hue": r["hue"], "rating": r["rating"], "text": r["text"],
              "game": r["game"], "reply": r["reply"], "at": r["created_at"]} for r in reviews.listing(conn, limit=30)]
    return {"total": s["total"], "avg": s["avg"], "pct": s["pct"], "items": items}


@router.post("/api/ping")
async def api_ping(request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    """«Я в сети» каждые 15 с, пока мини-приложение открыто; в ответ — кто ждёт соперников в гонке."""
    from . import race
    tg = _tg(request, config)
    if not tg:
        return _deny()
    user = _account(conn, tg)
    race.seen(conn, user["id"], (tg.get("first_name") or tg.get("username") or "")[:16], "app")
    return race.lobby(conn, user["id"])


@router.post("/api/history")
async def api_history(request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    tg = _tg(request, config)
    if not tg:
        return _deny()
    user = _account(conn, tg)
    rows = conn.execute("SELECT public_id, product_name, total_micro, status, created_at FROM orders "
                        "WHERE user_id = ? ORDER BY id DESC LIMIT 30", (user["id"],)).fetchall()
    items = [{"title": r["product_name"], "price": r["total_micro"], "status": r["status"], "at": r["created_at"],
              "ref": r["public_id"]} for r in rows]
    for g in tggifts.orders(conn, user_id=user["id"], limit=30):
        items.append({"title": f"{g['emoji'] or '🎁'} Gift ⭐{g['star_count']} → {g['recipient'] or '…'}",
                      "price": g["price_micro"], "status": g["status"], "status_title": g["status_title"],
                      "at": g["created_at"], "ref": refs.ref("gift", g["id"]),
                      "link": f"https://t.me/{db.get_setting(conn, 'gifts.bot_username') or ''}?start=g_{g['link_token']}"
                      if g["status"] == "awaiting_recipient" else ""})
    items.sort(key=lambda x: x["at"], reverse=True)
    return {"items": items[:40]}


@router.post("/api/session")
async def api_session(request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    """«Пополнить» — открыть страницу пополнения сайта уже под этим аккаунтом (вход по подписи Telegram)."""
    tg = check_init(request.headers.get("x-tg-init", ""), config.gift_bot_token, ttl=3600)
    if not tg:
        return _deny()
    user = _account(conn, tg)
    from .web import _record_login
    request.session["user_id"] = user["id"]
    request.session["tg_app"] = 1   # сайт внутри Telegram: показать системную кнопку «Назад»
    _record_login(conn, request, user["id"])
    body = await request.json()
    to = SITE_PAGES.get(str(body.get("to") or ""))
    if to:
        return {"url": to}
    need = str(body.get("need") or "")
    return {"url": "/panel/balance" + (f"?amount={int(need) / 10_000:.2f}" if need.isdigit() and int(need) else "")}


def _need(user, total: int) -> dict[str, Any]:
    return {"ok": False, "need": max(0, total - user["balance_micro"]),
            "error": "Маблағ кифоя нест — балансро пур кунед. / Не хватает денег — пополните баланс."}


@router.post("/api/buy")
async def api_buy(request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    tg = _tg(request, config)
    if not tg:
        return _deny()
    body = await request.json()
    user = _account(conn, tg)
    if jumuah.blocks(config, user, SOURCE):
        return {"ok": False, "error": jumuah.MESSAGE}
    kind = str(body.get("type") or "")
    to_friend = body.get("to") == "friend"
    username = str(body.get("username") or "").strip()
    if to_friend and not USERNAME_RE.match(username):
        return {"ok": False, "error": "Ники дӯстро нависед, масалан @username / Укажите ник друга, например @username"}
    if not to_friend:
        username = tg.get("username") or ""

    if kind == "gift":
        return _buy_gift(conn, config, user, tg, body, to_friend, username)

    if not username:
        return {"ok": False, "error": "Дар Telegram username гузоред (Танзимот → Username) / "
                                      "Задайте username в настройках Telegram"}
    if kind == "stars":
        pid, qty = "tg-stars", int(body.get("qty") or 0)
    elif kind == "premium":
        pid, qty = str(body.get("product_id") or ""), 1
    else:
        return {"ok": False, "error": "?"}
    p = catalog.get_product(conn, pid)   # Stars и Premium выключены — get_product их не отдаёт
    if p is None or p["kind"] not in ("telegram_stars", "telegram_premium"):
        return {"ok": False, "error": "Мол дастрас нест. / Товар недоступен."}
    fields = {f["key"]: "@" + username.lstrip("@") for f in p["fields"]}
    try:
        order, _ = orders.create_order(conn, config, request.app.state.supplier, user, product_id=pid, quantity=qty,
                                       fields=fields, client_idem_key="tgapp-" + str(body.get("idem") or uuid.uuid4())[:64],
                                       source=SOURCE)
    except orders.OrderError as exc:
        if exc.code == "insufficient_balance":
            total = orders.quote(config, user, p, qty)["total_micro"]
            return _need(user, total)
        return {"ok": False, "error": str(exc)}
    _watch(conn, "order", order["id"], tg)
    return {"ok": True, "message": f"✅ Фармоиш № {order['public_id']} қабул шуд — дар 1–5 дақиқа мерасад. "
                                   f"/ Заказ № {order['public_id']} принят.",
            "order": order["public_id"], "balance": accounts.get_user(conn, user["id"])["balance_micro"]}


def _buy_gift(conn, config: Config, user, tg: dict[str, Any], body: dict, to_friend: bool, username: str) -> dict:
    gift_id = str(body.get("gift_id") or "")
    text = str(body.get("text") or "")
    if to_friend:
        known = tggifts.find_username(conn, username)
        rid, rname = (int(known["tg_id"]), "@" + username.lstrip("@")) if known else (None, "@" + username.lstrip("@"))
    else:
        rid, rname = int(tg["id"]), tg.get("first_name") or ("Себе" if tgnotify.lang_of(tg) == "ru" else "Худам")
    try:
        o = tggifts.buy(conn, config, user, gift_id, recipient_id=rid, recipient=rname, text=text)
    except tggifts.GiftError as exc:
        if "баланс" in str(exc):
            g = conn.execute("SELECT star_count FROM tg_gifts WHERE id = ?", (gift_id,)).fetchone()
            return _need(user, tggifts.price_micro(conn, config, user, g["star_count"]) if g else 0)
        return {"ok": False, "error": str(exc)}
    _watch(conn, "gift", o["id"], tg)
    bot = db.get_setting(conn, "gifts.bot_username") or ""
    out = {"ok": True, "balance": accounts.get_user(conn, user["id"])["balance_micro"], "ref": refs.ref("gift", o["id"])}
    if o["status"] == "awaiting_recipient":
        out["link"] = f"https://t.me/{bot}?start=g_{o['link_token']}"
        out["message"] = (f"🎁 № {out['ref']}. Пардохт шуд! Ин пайвандро ба дӯстатон фиристед — ӯ Start-ро пахш кунад, тӯҳфа мерасад. "
                          "/ Оплачено! Отправьте ссылку другу — он нажмёт Start и получит подарок.")
    else:
        out["message"] = (f"🎁 № {out['ref']}. Тӯҳфа фиристода мешавад — дар чанд сония мерасад. "
                          "/ Подарок отправляется.")
    return out


# ── Пополнение прямо в мини-приложении (без перехода на сайт) ──────────────


def _pay_info(request: Request, conn, config: Config, user) -> dict[str, Any]:
    """Способы оплаты как на сайте (из СНГ — только крипта), курс и минимум."""
    from . import dcvideo, payments
    from .web import _crypto_only, _pay_methods
    conf = payments.settings(conn, config)
    methods = [{"code": m["code"], "title": m["title"], "icon": m["icon_url"], "auto": m["auto"],
                "currency": m["currency"], "net": m["net_short"], "network": m["network"],
                "details": "" if m["auto"] else m["details"], "min_usd": m["min_usd"], "max_usd": m["max_usd"]}
               for m in _pay_methods(request, conn, config, user["id"])]
    video = dcvideo.needed(conn, user["id"], "site")
    return {"methods": methods, "min_tjs": str(conf["min_tjs"]), "min_usd": str(conf["min_usd"]),
            "crypto_only": _crypto_only(request),
            "dc_video": dcvideo.src(config, video) if video else ""}


def _pay_view(conn, config: Config, pid: int) -> dict[str, Any]:
    from . import cryptopay, dcbank, payments
    row = conn.execute("SELECT * FROM payments WHERE id = ?", (pid,)).fetchone()
    p = payments.public(conn, config, row)
    p["left"] = cryptopay.seconds_left(row["created_at"]) if row["auto_kind"] in ("trc20", "bybit") else 0
    p["receipt_after"] = dcbank.receipt_after_min(conn) * 60 if row["auto_kind"] == "dcbank" else 0
    return p


@router.post("/api/topup/info")
async def api_topup_info(request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    tg = _tg(request, config)
    if not tg:
        return _deny()
    return _pay_info(request, conn, config, _account(conn, tg))


@router.post("/api/topup")
async def api_topup(request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    """Создать заявку: автоплатёж (крипта, «Душанбе Сити · авто») — экран оплаты; обычный перевод — сразу с чеком."""
    tg = _tg(request, config)
    if not tg:
        return _deny()
    from . import dcvideo, payments, rates
    from .tgbot import send_receipt
    from .web import _pay_methods
    form = await request.form()
    user = _account(conn, tg)
    method = str(form.get("method") or "")
    if not any(m["code"] == method for m in _pay_methods(request, conn, config)):
        return {"ok": False, "error": "Ин тарзи пардохт дастрас нест. / Способ оплаты недоступен."}
    file = form.get("receipt")
    data = await file.read(payments.MAX_RECEIPT_BYTES + 1) if file is not None and getattr(file, "filename", "") else b""
    auto = payments.is_auto(conn, config, method)
    if auto:
        data = b""
        chosen = next((m for m in payments.methods(conn, config) if m["code"] == method), {})
        if chosen.get("auto") == "dcbank" and dcvideo.needed(conn, user["id"], "site"):
            if form.get("agree") != "1":
                return {"ok": False, "error": "Аввал видеоро бинед ва қайд кунед, ки фаҳмидед. / "
                                              "Сначала посмотрите видео и отметьте, что поняли.", "video": True}
            dcvideo.ack(conn, user["id"], "site")
    elif not data:
        return {"ok": False, "error": "Чеки пардохтро замима кунед — акс ё PDF. / Прикрепите чек об оплате — фото или PDF."}
    rates.refresh(conn, config, rates.PAYMENT_SECONDS)
    from . import paycards
    details = paycards.all_details(conn, method, payments.settings(conn, config)["details"].get(method, ""))
    seen = payments.read_receipt(config, data, details) if data else None
    try:
        with db.tx(conn):
            pid = payments.create(conn, config, user, method, str(form.get("amount") or ""), "",
                                  amount_tjs=str(form.get("amount_tjs") or ""))
            if data:
                payments.attach_receipt(conn, config, user["id"], pid, data, seen=seen)
        payments.start_auto(conn, config, pid)
    except payments.PaymentError as exc:
        return {"ok": False, "error": str(exc)}
    _watch(conn, "pay", pid, tg)
    row = conn.execute("SELECT auto_kind FROM payments WHERE id = ?", (pid,)).fetchone()
    if not row["auto_kind"]:
        send_receipt(conn, config, pid)
        return {"ok": True, "done": True, "message": "✅ Чек гирифта шуд — пас аз санҷиш баланс пур мешавад. "
                                                      "/ Чек получен — после проверки баланс пополнится."}
    return {"ok": True, "pay": _pay_view(conn, config, pid)}


@router.post("/api/topup/status")
async def api_topup_status(request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    tg = _tg(request, config)
    if not tg:
        return _deny()
    from . import cryptopay
    user = _account(conn, tg)
    pid = int((await request.json()).get("id") or 0)
    row = conn.execute("SELECT status, auto_kind FROM payments WHERE id = ? AND user_id = ?", (pid, user["id"])).fetchone()
    if row is None:
        return {"status": "missing"}
    if row["status"] == "pending" and row["auto_kind"]:
        cryptopay.check_all(conn, config)
        cryptopay.expire(conn, pid)
        row = conn.execute("SELECT status FROM payments WHERE id = ?", (pid,)).fetchone()
    return {"status": row["status"], "balance": accounts.get_user(conn, user["id"])["balance_micro"]}


@router.post("/api/topup/receipt")
async def api_topup_receipt(request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    """«Душанбе Сити»: перевод не нашёлся сам — клиент присылает чек, админ проверит."""
    tg = _tg(request, config)
    if not tg:
        return _deny()
    from . import payments
    from .tgbot import send_receipt
    form = await request.form()
    user = _account(conn, tg)
    pid = int(form.get("id") or 0)
    file = form.get("receipt")
    data = await file.read(payments.MAX_RECEIPT_BYTES + 1) if file is not None and getattr(file, "filename", "") else b""
    try:
        payments.attach_receipt(conn, config, user["id"], pid, data)
    except payments.PaymentError as exc:
        return {"ok": False, "error": str(exc)}
    send_receipt(conn, config, pid)
    return {"ok": True, "message": "✅ Чек гирифта шуд — санҷида баланс пур мекунем. / Чек получен, проверим и пополним."}


# ── Гонка: 3D-игра в мини-приложении (race.py). Денег нет — только игровые монеты на цвет машины ──

@router.get("/race")
def race_page(request: Request, g: str = "", config: Config = Depends(get_config)):
    code = "".join(c for c in g.upper() if c.isalnum())[:8]      # ссылка-приглашение в группу друга
    return templates.TemplateResponse(request, "tg_race.html", {"site_name": config.site_name, "group_code": code})


@router.post("/api/race/{action}")
async def api_race(action: str, request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    from . import race
    tg = check_init(request.headers.get("x-tg-init", ""), config.gift_bot_token, ttl=6 * 3600)
    if not tg:
        return _deny()
    user = _account(conn, tg)
    name = (tg.get("first_name") or tg.get("username") or "Игрок")[:16]
    try:
        body = await request.json()
    except ValueError:
        body = {}
    try:
        if action == "profile":
            race.seen(conn, user["id"], name, "garage")
            return {**race.profile(conn, user["id"], name, config.tz_offset), "me": user["id"], "name": name,
                    "top": race.top(conn, period="week", tz_offset=config.tz_offset),
                    "stats": race.stats(conn, user["id"], config.tz_offset), "lobby": race.lobby(conn, user["id"]),
                    "bot": db.get_setting(conn, "gifts.bot_username") or ""}
        if action == "lobby":
            race.seen(conn, user["id"], name, str(body.get("place") or "garage"))
            return race.lobby(conn, user["id"])
        if action == "top":
            period = str(body.get("period") or "week")
            return {"top": race.top(conn, period=period if period in ("day", "week", "all") else "week",
                                    tz_offset=config.tz_offset), "stats": race.stats(conn, user["id"], config.tz_offset)}
        if action == "join":
            race.seen(conn, user["id"], name, "race")
            return race.join(conn, user["id"], name, config.tz_offset, solo=bool(body.get("solo")))
        if action.startswith("group_"):       # своя группа: создать, войти по коду, старт (хозяин), выйти
            rooms = race.RaceGame(conn, config.tz_offset).rooms
            if action == "group_create":
                return rooms.group_create(user["id"], name)
            if action == "group_join":
                return rooms.group_join(user["id"], name, str(body.get("code") or ""))
            if action == "group_start":
                return rooms.group_start(user["id"], int(body.get("room") or 0))
            if action == "group_leave":
                return rooms.group_leave(user["id"], int(body.get("room") or 0))
        if action == "tick":
            return race.tick(conn, user["id"], int(body.get("room") or 0), float(body.get("z") or 0),
                             float(body.get("x") or 0), float(body.get("v") or 0))
        if action == "finish":
            return race.finish(conn, user["id"], int(body.get("room") or 0), int(body.get("ms") or 0), config.tz_offset)
        if action == "upgrade":
            return race.upgrade(conn, user["id"], str(body.get("key") or ""), config.tz_offset)
        if action == "shop":
            return race.shop(conn, user["id"], str(body.get("color") or ""), config.tz_offset)
    except race.RaceError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except (TypeError, ValueError):
        return JSONResponse({"error": "Неверные данные."}, status_code=400)
    return JSONResponse({"error": "Нет такого действия."}, status_code=404)
