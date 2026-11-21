"""Веб: мини-приложение /app и его API. Каждый запрос подписан Telegram (initData) — чужой не пройдёт."""
from __future__ import annotations

import hashlib
import secrets
import threading
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db, receipt, shop
from .config import ROOT, Config
from .money import fmt, to_diram
from .tg import Bot, check_init_data

STATIC = ROOT / "static"
MAX_RECEIPT = 10 * 1024 * 1024


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


def create_app(config: Config, bot: Bot | None = None) -> FastAPI:
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
        if request.url.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/", response_class=HTMLResponse)
    def root():
        name = config.name
        return (f'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<title>{name}</title><body style="margin:0;display:grid;place-items:center;min-height:100vh;background:#0B0B0B;'
                f'color:#fff;font:700 22px system-ui;letter-spacing:4px">{name.upper()}</body>')

    @app.get("/app")
    def mini_app():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/healthz")
    def health():
        return {"ok": True}

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

    return app


async def _in_thread(fn, *args):
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(fn, *args)
