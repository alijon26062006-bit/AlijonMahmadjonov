"""Сайт: главная, регистрация/вход, документация и кабинет клиента."""

from __future__ import annotations

import json
import sqlite3
import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse

from . import accounts, catalog, orders
from .config import Config
from .deps import LoginRequired, check_csrf, flash, get_config, get_conn, render, session_user
from .suppliers import KINDS

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
    cats = catalog.categories(conn)
    by_kind: dict[str, list] = {}
    for c in cats:
        by_kind.setdefault(c["kind"], []).append(c)
    total = sum(c["n"] for c in cats)
    return render(request, "home.html", {
        "user": session_user(request, conn),
        "by_kind": by_kind,
        "total_products": total,
        "markups": config.markups,
    })


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
    if config.require_approval:
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
    return _redirect("/admin" if user["role"] == "admin" else "/panel")


@router.post("/logout", dependencies=[Depends(check_csrf)])
def logout(request: Request):
    request.session.clear()
    return _redirect("/")


def _ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")


# ── Кабинет ──────────────────────────────────────────────────


@router.get("/panel")
def panel_home(request: Request, user=Depends(panel_user), conn=Depends(get_conn)):
    summary = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(total_micro), 0) AS spent FROM orders "
        "WHERE user_id = ? AND status = 'completed'",
        (user["id"],),
    ).fetchone()
    recent = conn.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user["id"],)
    ).fetchall()
    has_key = conn.execute(
        "SELECT 1 FROM api_keys WHERE user_id = ? AND revoked_at IS NULL", (user["id"],)
    ).fetchone() is not None
    return render(request, "panel/home.html", {
        "user": user, "summary": summary, "recent": recent, "has_key": has_key, "kinds": KINDS,
    })


@router.get("/panel/catalog")
def panel_catalog(
    request: Request, kind: str = "", q: str = "", category: str = "",
    user=Depends(panel_user), conn=Depends(get_conn), config: Config = Depends(get_config),
):
    items = [catalog.public_view(p, accounts.markup_for(user, config, p["kind"])) for p in
             catalog.list_products(conn, kind=kind if kind in KINDS else "", q=q[:100], category_id=category)]
    groups: dict[str, list] = {}
    for item in items:
        groups.setdefault(f"{item['kind_title']} · {item['category_name']}", []).append(item)
    return render(request, "panel/catalog.html", {
        "user": user, "groups": groups, "kind": kind, "q": q, "kinds": KINDS, "count": len(items),
    })


@router.get("/panel/buy/{product_id}")
def panel_buy_form(product_id: str, request: Request, user=Depends(panel_user), conn=Depends(get_conn),
                   config: Config = Depends(get_config)):
    p = catalog.get_product(conn, product_id)
    if p is None:
        flash(request, "Товар недоступен.", "error")
        return _redirect("/panel/catalog")
    view = catalog.public_view(p, accounts.markup_for(user, config, p["kind"]))
    return render(request, "panel/buy.html", {
        "user": user, "p": view, "form": {}, "idem": str(uuid.uuid4()),
    })


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
        view = catalog.public_view(p, accounts.markup_for(user, config, p["kind"]))
        return render(request, "panel/buy.html", {
            "user": accounts.get_user(conn, user["id"]), "p": view, "error": str(exc),
            "form": {**fields, "quantity": form.get("quantity", "")}, "idem": str(uuid.uuid4()),
        }, 400)
    return _redirect(f"/panel/orders/{order['public_id']}")


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
def panel_balance(request: Request, user=Depends(panel_user)):
    return render(request, "panel/balance.html", {"user": user})


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
        key = accounts.create_api_key(conn, user["id"], name)
    except accounts.AccountError as exc:
        flash(request, str(exc), "error")
        return _redirect("/panel/api")
    request.session["new_api_key"] = key
    return _redirect("/panel/api")


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

