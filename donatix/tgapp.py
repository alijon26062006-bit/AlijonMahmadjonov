"""Мини-приложение Telegram /tg: Stars, Premium, Подарки — одна страница, пять вкладок.

Кто открыл — по подписи Telegram (initData, подписана токеном бота мини-приложения). Аккаунт тот же,
что у бота-магазина: Telegram ID → аккаунт Donatix (общий баланс, заказы, рефералка).
Stars и Premium — обычные заказы каталога (source='tgapp'), подарки — tggifts.
"""

from __future__ import annotations

import re
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
    return check_init(request.headers.get("x-tg-init", ""), config.gift_bot_token)


def _deny() -> JSONResponse:
    return JSONResponse({"error": "Откройте магазин из Telegram-бота."}, status_code=403)


def _account(conn, tg: dict[str, Any], start: str = ""):
    """Аккаунт Donatix этого Telegram (тот же, что в боте-магазине)."""
    from .shopbot import ensure_user
    su = ensure_user(conn, int(tg["id"]), tg.get("first_name") or "", start, username=tg.get("username") or "")
    tggifts.remember_user(conn, tg)
    if start.startswith("r_"):
        from . import referrals
        referrals.attach(conn, su["user_id"], start[2:])
    return accounts.get_user(conn, su["user_id"])


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


def _feed(conn) -> list[dict[str, Any]]:
    """Последние покупки всех: имя покупателя (только имя из Telegram), что купил, когда."""
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
            what = f"Premium · {m.group(1) if m else ''} моҳ"
        else:
            what = f"{r['emoji'] or '🎁'} Gift · {r['qty']}⭐"
        out.append({"who": who or "Харидор", "what": what, "kind": r["kind"], "at": r["at"]})
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
        "me": {"id": tg["id"], "name": tg.get("first_name") or "", "username": tg.get("username") or "",
               "photo": tg.get("photo_url") or "", "balance": user["balance_micro"]},
        "stats": _stats(conn, user["id"]),
        "rate": _rate(conn, config),
        "stars": _stars(conn, config, user),
        "premium": _premium(conn, config, user),
        "gifts": tggifts.listing(conn, config, user) if tggifts.enabled(config) else [],
        "feed": _feed(conn),
        "ref": {"percent": referrals.percent(conn), "invited": referrals.stats(conn, user["id"])["invited"],
                "link": f"https://t.me/{bot}?start=r_{referrals.code_for(conn, user['id'])}" if bot else ""},
        "bot": bot,
        "friday": jumuah.MESSAGE if jumuah.closed(config) else "",
        "pay": _pay_info(request, conn, config, user),
    }


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
        return {"ok": False, "error": "Товар недоступен."}
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
    tgnotify.add(conn, "order", order["id"], tg)
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
        rid, rname = int(tg["id"]), tg.get("first_name") or "Худам"
    try:
        o = tggifts.buy(conn, config, user, gift_id, recipient_id=rid, recipient=rname, text=text)
    except tggifts.GiftError as exc:
        if "баланс" in str(exc):
            g = conn.execute("SELECT star_count FROM tg_gifts WHERE id = ?", (gift_id,)).fetchone()
            return _need(user, tggifts.price_micro(conn, config, user, g["star_count"]) if g else 0)
        return {"ok": False, "error": str(exc)}
    tgnotify.add(conn, "gift", o["id"], tg)
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
               for m in _pay_methods(request, conn, config)]
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
        return {"ok": False, "error": "Способ оплаты недоступен."}
    file = form.get("receipt")
    data = await file.read(payments.MAX_RECEIPT_BYTES + 1) if file is not None and getattr(file, "filename", "") else b""
    auto = payments.is_auto(conn, config, method)
    if auto:
        data = b""
        chosen = next((m for m in payments.methods(conn, config) if m["code"] == method), {})
        if chosen.get("auto") == "dcbank" and dcvideo.needed(conn, user["id"], "site"):
            if form.get("agree") != "1":
                return {"ok": False, "error": "Сначала посмотрите видео и отметьте, что поняли.", "video": True}
            dcvideo.ack(conn, user["id"], "site")
    elif not data:
        return {"ok": False, "error": "Прикрепите чек об оплате — фото или PDF."}
    rates.refresh(conn, config, rates.PAYMENT_SECONDS)
    details = payments.settings(conn, config)["details"].get(method, "")
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
    tgnotify.add(conn, "pay", pid, tg)
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
