"""Веб: мини-приложение /app и его API. Каждый запрос подписан Telegram (initData) — чужой не пройдёт."""
from __future__ import annotations

import hashlib
import secrets
import threading
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import db, receipt, shop
from .config import ROOT, Config
from .money import fmt, to_diram
from .tg import Bot, TgError, check_init_data

STATIC = ROOT / "static"
MAX_RECEIPT = 10 * 1024 * 1024
GIFT_TYPES = {"tgs": "application/json", "webm": "video/webm", "webp": "image/webp"}


def _sniff(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:5] == b"%PDF-":
        return "pdf"
    return None


def create_app(config: Config, bot: Bot | None = None, supplier=None) -> FastAPI:
    db.init(config.db_path)
    app = FastAPI(title=config.name, docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    def conn():
        return db.conn_for(config.db_path)

    def user(x_init_data: str = Header(default="")) -> dict[str, Any]:
        u = check_init_data(x_init_data, config.bot_token)
        if u is None:
            raise HTTPException(401, "Откройте магазин из Telegram. / Магазинро аз Telegram кушоед.")
        row = shop.touch_user(conn(), u)
        if row["banned"]:
            raise HTTPException(403, "Доступ закрыт.")
        return dict(row)

    @app.exception_handler(shop.ShopError)
    def _shop_error(request: Request, exc: shop.ShopError):
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    @app.middleware("http")
    async def _headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"   # поисковики не узнают о скрытом адресе
        if request.url.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/")
    def root():
        raise HTTPException(404)   # скрытый адрес: снаружи ничего не показываем

    @app.get("/app")
    def mini_app():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/healthz")
    def health():
        return {"ok": True}

    gift_lock = threading.Lock()

    @app.get("/gift/{gift_id}")
    def gift_animation(gift_id: str):
        """Анимация подарка — та же, что в Telegram (стикер подарка). Скачивается один раз и хранится у нас."""
        g = shop.gift_for(conn(), gift_id)
        if not g or not g.get("file") or g.get("fmt") not in GIFT_TYPES or bot is None:
            raise HTTPException(404)
        safe = hashlib.sha256(str(g["id"]).encode()).hexdigest()[:24]
        path = Path(config.db_path).parent / "gifts" / f"{safe}.{g['fmt']}"
        if not path.exists():
            with gift_lock:
                if not path.exists():
                    try:
                        data = bot.download(g["file"])
                    except TgError:
                        raise HTTPException(404) from None
                    path.parent.mkdir(parents=True, exist_ok=True)
                    tmp = path.with_suffix(".part")
                    tmp.write_bytes(data)
                    tmp.replace(path)
        headers = {"Cache-Control": "public, max-age=604800, immutable"}
        if g["fmt"] == "tgs":          # .tgs = Lottie JSON, сжатый gzip — браузер распакует сам
            headers["Content-Encoding"] = "gzip"
        return Response(path.read_bytes(), media_type=GIFT_TYPES[g["fmt"]], headers=headers)

    def me_view(u: dict) -> dict[str, Any]:
        c = conn()
        orders = c.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 30", (u["id"],)).fetchall()
        waiting = c.execute("SELECT * FROM topups WHERE user_id = ? AND status IN ('waiting','pending') ORDER BY id DESC LIMIT 1",
                            (u["id"],)).fetchone()
        return {"ok": True, "name": config.name, "bot": db.get_setting(c, "bot_username"),
                "user": {"id": u["id"], "first_name": u["first_name"], "username": u["username"], "lang": u["lang"],
                         "balance": c.execute("SELECT balance FROM users WHERE id = ?", (u["id"],)).fetchone()[0]},
                "catalog": shop.catalog(c), "methods": shop.methods(c), "support": config.support,
                "orders": [shop.public_order(o) for o in orders],
                "admin": shop.is_admin(c, config, u["id"]),
                "topup": shop.topup_view(c, waiting) if waiting else None}

    @app.get("/api/me")
    def me(u=Depends(user)):
        return me_view(u)

    @app.post("/api/lang")
    async def lang(request: Request, u=Depends(user)):
        body = await request.json()
        v = "ru" if body.get("lang") == "ru" else "tj"
        conn().execute("UPDATE users SET lang = ? WHERE id = ?", (v, u["id"]))
        return {"ok": True, "lang": v}

    @app.post("/api/quote")
    async def quote(request: Request, u=Depends(user)):
        return {"ok": True, **shop.quote(conn(), await request.json())}

    @app.post("/api/order")
    async def order(request: Request, u=Depends(user)):
        o = shop.place_order(conn(), u["id"], await request.json())
        view = me_view(u)
        return {**view, "order": shop.public_order(o)}

    @app.post("/api/topup")
    async def topup(request: Request, u=Depends(user)):
        body = await request.json()
        try:
            amount = to_diram(body.get("amount") or 0)
        except Exception:  # noqa: BLE001
            raise shop.ShopError("Неверная сумма.") from None
        intent = body.get("intent") if isinstance(body.get("intent"), dict) else None
        if intent:   # пополняем ровно на недостающее для покупки
            q = shop.quote(conn(), intent)
            if intent.get("kind") != "gift" or intent.get("to"):
                shop.clean_username(intent.get("to") or "")
            bal = conn().execute("SELECT balance FROM users WHERE id = ?", (u["id"],)).fetchone()[0]
            need = q["price"] - bal
            amount = need if need >= 100 else q["price"]   # баланса хватает, но выбрал перевод — платит полную цену
        t = shop.create_topup(conn(), u["id"], str(body.get("method") or ""), amount, intent)
        return {"ok": True, "topup": shop.topup_view(conn(), t)}

    @app.post("/api/topup/{tid}/cancel")
    def topup_cancel(tid: int, u=Depends(user)):
        conn().execute("UPDATE topups SET status = 'cancelled', resolved_at = ? WHERE id = ? AND user_id = ? AND status = 'waiting'",
                       (db.now(), tid, u["id"]))
        return {"ok": True}

    @app.post("/api/topup/{tid}/receipt")
    async def topup_receipt(tid: int, file: UploadFile = File(...), u=Depends(user)):
        data = await file.read(MAX_RECEIPT + 1)
        if not data or len(data) > MAX_RECEIPT:
            raise shop.ShopError("Файл чека пустой или больше 10 МБ.")
        ext = _sniff(data)
        if not ext:
            raise shop.ShopError("Чек — фото (JPG, PNG, WEBP) или PDF.")
        c = conn()
        t = c.execute("SELECT * FROM topups WHERE id = ? AND user_id = ?", (tid, u["id"])).fetchone()
        if t is None or t["status"] != "waiting":
            raise shop.ShopError("Заявка не найдена или уже на проверке.")
        digest = hashlib.sha256(data).hexdigest()
        if c.execute("SELECT 1 FROM topups WHERE receipt_hash = ? AND status IN ('pending','paid')", (digest,)).fetchone():
            raise shop.ShopError("Этот чек уже присылали. / Ин чек аллакай фиристода шудааст.")
        card = c.execute("SELECT details FROM cards WHERE id = ?", (t["card_id"],)).fetchone()
        ours = "\n".join(r["details"] for r in shop.cards(c))   # все наши карты: клиент мог перевести на другую нашу
        seen = await _in_thread(receipt.read, config.openai_key, config.receipt_model, data, ext, ours)
        bad = receipt.refuse(seen, ours)
        if bad:
            raise shop.ShopError(bad)
        folder = Path(config.receipts_dir)
        folder.mkdir(parents=True, exist_ok=True)
        name = f"{tid}-{secrets.token_hex(6)}.{ext}"
        (folder / name).write_bytes(data)
        note = ""
        if seen:
            note = f"получатель «{seen['recipient']}», сумма {seen.get('amount')} {seen.get('currency')}"
        done = c.execute("UPDATE topups SET status = 'pending', receipt_file = ?, receipt_hash = ?, ai_note = ? "
                         "WHERE id = ? AND status = 'waiting'", (name, digest, note, tid)).rowcount
        if not done:
            raise shop.ShopError("Заявка уже на проверке.")
        if bot is not None:
            from .bot import notify_receipt
            threading.Thread(target=notify_receipt, args=(config, bot, db.connect(config.db_path), tid, data, ext),
                             daemon=True).start()
        return {"ok": True, "message": f"Чек получен — проверим и пополним баланс на {fmt(t['amount'])} с. "
                                       "/ Чек гирифта шуд — санҷида баланс пур мекунем."}

    # ── админ-панель (только для админов из SITORA_ADMIN_IDS) ──
    def admin(u=Depends(user)) -> dict[str, Any]:
        if not shop.is_admin(conn(), config, u["id"]):
            raise HTTPException(403, "Только для админа.")
        return u

    def order_row(o) -> dict[str, Any]:
        return {"id": o["id"], "user_id": o["user_id"], "title": o["title"], "to": o["recipient"], "price": o["price"],
                "status": o["status"], "error": o["error"], "supplier": o["supplier_order_id"] or "", "at": o["created_at"]}

    @app.get("/api/admin/summary")
    async def admin_summary(u=Depends(admin)):
        c = conn()
        q = lambda sql, *a: c.execute(sql, a).fetchone()   # noqa: E731
        today = q("SELECT COUNT(*), COALESCE(SUM(price),0) FROM orders WHERE created_at >= date('now') AND status != 'failed'")
        week = q("SELECT COUNT(*), COALESCE(SUM(price),0) FROM orders WHERE created_at >= date('now','-6 days') AND status != 'failed'")
        days = c.execute("SELECT substr(created_at,1,10) d, COALESCE(SUM(price),0) s FROM orders WHERE created_at >= date('now','-6 days') "
                         "AND status != 'failed' GROUP BY d").fetchall()
        sup = bal = None
        if supplier is not None:
            try:
                sup = str(await _in_thread(supplier.balance))
            except Exception as exc:  # noqa: BLE001
                sup = "нет связи: " + str(exc)[:60]
        if bot is not None:
            bal = ((await _in_thread(bot.safe, "getMyStarBalance")) or {}).get("amount")
        pend = c.execute("SELECT t.*, u.username, u.first_name FROM topups t JOIN users u ON u.id = t.user_id "
                         "WHERE t.status = 'pending' ORDER BY t.id").fetchall()
        card = {r["id"]: r["details"] for r in c.execute("SELECT id, details FROM cards")}
        return {"ok": True,
                "users": q("SELECT COUNT(*) FROM users")[0], "today": {"n": today[0], "sum": today[1]},
                "week": {"n": week[0], "sum": week[1]}, "days": [{"d": r["d"], "s": r["s"]} for r in days],
                "supplier": sup, "bot_stars": bal,
                "settings": {"rate": str(shop.rate(c)), "markup": str(shop.markup(c)),
                             "gift_star": fmt(int(db.get_setting(c, "gift_star_diram") or 0)) if db.get_setting(c, "gift_star_diram") else ""},
                "topups": [{"id": t["id"], "user_id": t["user_id"], "who": (t["first_name"] or "") + (" @" + t["username"] if t["username"] else ""),
                            "amount": t["amount"], "method": shop.METHODS.get(t["method"], t["method"]), "card": card.get(t["card_id"], ""),
                            "ai": t["ai_note"], "at": t["created_at"]} for t in pend],
                "attention": [order_row(o) for o in c.execute("SELECT * FROM orders WHERE status IN ('attention','processing','awaiting_recipient','new','paid','sending') ORDER BY id DESC LIMIT 50")],
                "recent": [order_row(o) for o in c.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 30")],
                "cards": [{"id": r["id"], "method": r["method"], "title": shop.METHODS.get(r["method"], r["method"]), "details": r["details"]}
                          for r in shop.cards(c)],
                "methods": [{"code": k, "title": v} for k, v in shop.METHODS.items()]}

    @app.get("/api/admin/receipt/{tid}")
    def admin_receipt(tid: int, u=Depends(admin)):
        t = conn().execute("SELECT receipt_file FROM topups WHERE id = ?", (tid,)).fetchone()
        if not t or not t["receipt_file"]:
            raise HTTPException(404, "Нет чека")
        path = Path(config.receipts_dir) / Path(t["receipt_file"]).name
        return FileResponse(path, headers={"Cache-Control": "private, no-store"})

    @app.post("/api/admin/topup/{tid}")
    async def admin_topup(tid: int, request: Request, u=Depends(admin)):
        body = await request.json()
        from .bot import finish_topup
        t = await _in_thread(finish_topup, config, bot, db.connect(config.db_path), tid, bool(body.get("ok")),
                             u["first_name"] or str(u["id"]), str(body.get("note") or "")[:200])
        if t is None:
            raise shop.ShopError("Эту заявку уже решили.")
        return {"ok": True}

    @app.post("/api/admin/order/{oid}")
    async def admin_order(oid: int, request: Request, u=Depends(admin)):
        act = (await request.json()).get("action")
        c = conn()
        o = c.execute("SELECT * FROM orders WHERE id = ?", (oid,)).fetchone()
        if o is None:
            raise shop.ShopError("Заказ не найден.")
        if act == "refund":
            if not shop.refund(c, oid, "отменён администратором"):
                raise shop.ShopError("Заказ уже завершён — возврат не сделан.")
            if bot:
                bot.safe("sendMessage", chat_id=o["user_id"], text=f"↩️ Заказ № {oid} отменён, {fmt(o['price'])} с. вернулись на баланс.")
        elif act == "done":
            done = c.execute("UPDATE orders SET status = ?, updated_at = ? WHERE id = ? AND status NOT IN ('completed','sent','failed')",
                             ("sent" if o["kind"] == "gift" else "completed", db.now(), oid)).rowcount
            if not done:
                raise shop.ShopError("Заказ уже завершён.")
        elif act == "retry":   # повтор тем же ключом — второго заказа не будет
            c.execute("UPDATE orders SET status = CASE WHEN kind = 'gift' THEN 'paid' ELSE 'new' END, tries = 0, updated_at = ? "
                      "WHERE id = ? AND status = 'attention'", (db.now(), oid))
        else:
            raise shop.ShopError("Неизвестное действие.")
        return {"ok": True}

    @app.post("/api/admin/cards")
    async def admin_card_add(request: Request, u=Depends(admin)):
        body = await request.json()
        method, details = str(body.get("method") or ""), str(body.get("details") or "").strip()[:300]
        if method not in shop.METHODS or len(details) < 6:
            raise shop.ShopError("Выберите банк и впишите реквизиты.")
        conn().execute("INSERT INTO cards (method, details, created_at) VALUES (?, ?, ?)", (method, details, db.now()))
        return {"ok": True}

    @app.post("/api/admin/cards/{cid}/off")
    def admin_card_off(cid: int, u=Depends(admin)):
        conn().execute("UPDATE cards SET active = 0 WHERE id = ?", (cid,))
        return {"ok": True}

    @app.post("/api/admin/settings")
    async def admin_settings(request: Request, u=Depends(admin)):
        from decimal import Decimal, InvalidOperation
        body, c = await request.json(), conn()
        try:
            if body.get("rate") not in (None, ""):
                v = Decimal(str(body["rate"]).replace(",", "."))
                if not Decimal(5) <= v <= Decimal(30):
                    raise shop.ShopError("Курс — от 5 до 30 сомони за доллар.")
                db.set_setting(c, "rate", str(v))
            if body.get("markup") not in (None, ""):
                v = Decimal(str(body["markup"]).replace(",", "."))
                if not Decimal(0) <= v <= Decimal(100):
                    raise shop.ShopError("Наценка — от 0 до 100%.")
                db.set_setting(c, "markup", str(v))
            if "gift_star" in body:
                db.set_setting(c, "gift_star_diram", str(to_diram(body["gift_star"])) if str(body["gift_star"]).strip() else "")
        except InvalidOperation:
            raise shop.ShopError("Неверное число.") from None
        return {"ok": True}

    @app.get("/api/admin/user")
    def admin_user(q: str, u=Depends(admin)):
        c = conn()
        q = q.strip().lstrip("@")
        row = c.execute("SELECT * FROM users WHERE id = ? OR lower(username) = lower(?)",
                        (int(q) if q.isdigit() else -1, q)).fetchone()
        if row is None:
            raise shop.ShopError("Клиент не найден (ID или @username).")
        return {"ok": True, "user": {"id": row["id"], "name": row["first_name"], "username": row["username"], "balance": row["balance"],
                                     "banned": bool(row["banned"]), "since": row["created_at"]},
                "orders": [order_row(o) for o in c.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 10", (row["id"],))],
                "ledger": [{"delta": r["delta"], "reason": r["reason"], "at": r["created_at"]}
                           for r in c.execute("SELECT * FROM ledger WHERE user_id = ? ORDER BY id DESC LIMIT 10", (row["id"],))]}

    @app.post("/api/admin/user/{uid}")
    async def admin_user_edit(uid: int, request: Request, u=Depends(admin)):
        body, c = await request.json(), conn()
        if body.get("amount") not in (None, ""):
            with db.tx(c):
                shop.move(c, uid, to_diram(body["amount"]), str(body.get("note") or "Изменено администратором")[:120], "admin")
        if "banned" in body:
            c.execute("UPDATE users SET banned = ? WHERE id = ?", (1 if body["banned"] else 0, uid))
        return {"ok": True}

    return app


async def _in_thread(fn, *args):
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(fn, *args)
