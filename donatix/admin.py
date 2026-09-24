"""Админка: клиенты, балансы, заказы, каталог, состояние поставщика."""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from . import accounts, catalog, db, orders, worker
from .config import PAY_METHODS, TIERS, Config
from .deps import Forbidden, LoginRequired, check_csrf, flash, get_config, get_conn, render, session_user
from .money import MoneyError, apply_markup, fmt, fmt_unit, to_decimal, to_micro
from .suppliers import KINDS, SupplierError

router = APIRouter(prefix="/admin", include_in_schema=False)


def admin_user(request: Request, conn: sqlite3.Connection = Depends(get_conn)) -> sqlite3.Row:
    user = session_user(request, conn)
    if user is None:
        raise LoginRequired()
    if user["role"] != "admin":
        raise Forbidden("Нет доступа.")
    return user


def _back(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


@router.get("")
def dashboard(request: Request, admin=Depends(admin_user), conn=Depends(get_conn),
              config: Config = Depends(get_config)):
    counts = {
        "pending_users": conn.execute("SELECT COUNT(*) FROM users WHERE status = 'pending'").fetchone()[0],
        "clients": conn.execute("SELECT COUNT(*) FROM users WHERE role = 'client'").fetchone()[0],
        "attention": conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'attention'").fetchone()[0],
        "processing": conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'processing'").fetchone()[0],
        "pending_payments": conn.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'").fetchone()[0],
        "failed_today": conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'failed' AND created_at >= date('now')"
                                     ).fetchone()[0],
        "products": conn.execute("SELECT COUNT(*) FROM products WHERE active = 1").fetchone()[0],
        "client_balances": conn.execute(
            "SELECT COALESCE(SUM(balance_micro), 0) FROM users WHERE role = 'client'").fetchone()[0],
    }
    return render(request, "admin/dashboard.html", {
        "user": admin,
        "counts": counts,
        "today": orders.stats(conn, 1),
        "month": orders.stats(conn, 30),
        "days": orders.daily(conn, 14),
        "top": orders.top_clients(conn),
        "supplier_balance": worker.supplier_balance_cached(conn),
        "supplier_balance_at": db.get_setting(conn, "supplier_balance_at"),
        "catalog_synced_at": db.get_setting(conn, "catalog_synced_at"),
        "supplier_name": config.supplier,
        "low": config.supplier_low_balance,
        "recent": conn.execute(
            "SELECT o.*, u.login FROM orders o JOIN users u ON u.id = o.user_id ORDER BY o.id DESC LIMIT 10"
        ).fetchall(),
    })


@router.post("/sync", dependencies=[Depends(check_csrf)])
def sync_now(request: Request, admin=Depends(admin_user), conn=Depends(get_conn),
             config: Config = Depends(get_config)):
    try:
        result = catalog.sync_catalog(conn, request.app.state.supplier)
        worker.check_supplier_balance(conn, config, request.app.state.supplier)
        flash(request, f"Каталог обновлён: {result['products']} товаров, выключено {result['disabled']}.")
    except SupplierError as exc:
        flash(request, f"Поставщик не ответил: {exc}", "error")
    return _back("/admin")


# ── Клиенты ──────────────────────────────────────────────────


@router.get("/users")
def users(request: Request, status: str = "", q: str = "", admin=Depends(admin_user), conn=Depends(get_conn)):
    where, args = "1=1", []
    if status in ("pending", "active", "blocked"):
        where += " AND status = ?"
        args.append(status)
    if q:
        where += " AND (email LIKE ? OR login LIKE ?)"
        args += [f"%{q}%", f"%{q}%"]
    rows = conn.execute(
        f"SELECT u.*, (SELECT COUNT(*) FROM orders o WHERE o.user_id = u.id AND o.status = 'completed') AS n_orders "
        f"FROM users u WHERE {where} ORDER BY (status = 'pending') DESC, id DESC LIMIT 200", args
    ).fetchall()
    return render(request, "admin/users.html", {"user": admin, "rows": rows, "status": status, "q": q})


@router.get("/users/{user_id}")
def user_detail(user_id: int, request: Request, admin=Depends(admin_user), conn=Depends(get_conn),
                config: Config = Depends(get_config)):
    client = accounts.get_user(conn, user_id)
    if client is None:
        flash(request, "Нет такого пользователя.", "error")
        return _back("/admin/users")
    return render(request, "admin/user.html", {
        "user": admin, "c": client, "tiers": TIERS, "markups": config.markups,
        "effective_markup": accounts.markup_for(client, config),
        "txs": conn.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 30",
                            (user_id,)).fetchall(),
        "orders": conn.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 20",
                               (user_id,)).fetchall(),
    })


@router.post("/users/{user_id}", dependencies=[Depends(check_csrf)])
def user_update(user_id: int, request: Request, status: str = Form(...), tier: str = Form(...),
                markup_override: str = Form(""), admin=Depends(admin_user), conn=Depends(get_conn)):
    if user_id == admin["id"] and status != "active":
        flash(request, "Нельзя отключить самого себя.", "error")
        return _back(f"/admin/users/{user_id}")
    before = accounts.get_user(conn, user_id)
    try:
        accounts.update_user_admin(conn, user_id, status=status, tier=tier, markup_override=markup_override)
        flash(request, "Сохранено.")
        if before and before["status"] != "active" and status == "active":
            from .notify import notify
            notify(conn, request.app.state.config, user_id,
                   "Аккаунт активирован — можно пополнять баланс и делать заказы.", "/panel")
    except accounts.AccountError as exc:
        flash(request, str(exc), "error")
    return _back(f"/admin/users/{user_id}")


@router.post("/users/{user_id}/balance", dependencies=[Depends(check_csrf)])
def user_balance(user_id: int, request: Request, amount: str = Form(...), note: str = Form(""),
                 admin=Depends(admin_user), conn=Depends(get_conn)):
    try:
        micro = to_micro(amount.replace(",", ".").replace("$", ""))
    except MoneyError:
        flash(request, "Сумма — число, например 100 или -5.50", "error")
        return _back(f"/admin/users/{user_id}")
    if micro == 0:
        flash(request, "Сумма не может быть нулём.", "error")
        return _back(f"/admin/users/{user_id}")
    text = note.strip() or ("Пополнение баланса" if micro > 0 else "Списание")
    try:
        with db.tx(conn):
            accounts.post_ledger(conn, user_id, micro, text, created_by=admin["id"])
    except accounts.InsufficientBalance:
        flash(request, "Столько списать нельзя: баланс уйдёт в минус.", "error")
        return _back(f"/admin/users/{user_id}")
    from .notify import notify
    notify(conn, request.app.state.config, user_id,
           (f"Баланс пополнен на ${fmt(micro)}" if micro > 0 else f"С баланса списано ${fmt(-micro)}") + f": {text}.",
           "/panel/transactions")
    flash(request, f"Баланс изменён на ${fmt(micro)}.")
    return _back(f"/admin/users/{user_id}")


# ── Заказы ───────────────────────────────────────────────────


@router.get("/orders")
def orders_list(request: Request, status: str = "", q: str = "", admin=Depends(admin_user), conn=Depends(get_conn)):
    where, args = "1=1", []
    if status in ("processing", "completed", "failed", "attention"):
        where += " AND o.status = ?"
        args.append(status)
    if q:
        where += " AND (o.public_id LIKE ? OR o.supplier_order_id LIKE ? OR o.product_name LIKE ? OR u.login LIKE ?)"
        args += [f"%{q}%"] * 4
    rows = conn.execute(
        f"SELECT o.*, u.login FROM orders o JOIN users u ON u.id = o.user_id WHERE {where} "
        f"ORDER BY (o.status = 'attention') DESC, o.id DESC LIMIT 200", args
    ).fetchall()
    return render(request, "admin/orders.html", {"user": admin, "rows": rows, "status": status, "q": q})


@router.get("/orders/{order_id}")
def order_detail(order_id: int, request: Request, admin=Depends(admin_user), conn=Depends(get_conn)):
    o = conn.execute("SELECT o.*, u.login, u.email FROM orders o JOIN users u ON u.id = o.user_id WHERE o.id = ?",
                     (order_id,)).fetchone()
    if o is None:
        flash(request, "Нет такого заказа.", "error")
        return _back("/admin/orders")
    delivery = json.loads(o["delivery_json"]) if o["delivery_json"] else None
    return render(request, "admin/order.html", {
        "user": admin, "o": o, "fields": json.loads(o["fields_json"] or "{}"),
        "delivery_pretty": json.dumps(delivery, ensure_ascii=False, indent=2) if delivery else "",
    })


@router.post("/orders/{order_id}/refund", dependencies=[Depends(check_csrf)])
def order_refund(order_id: int, request: Request, reason: str = Form(""), admin=Depends(admin_user),
                 conn=Depends(get_conn)):
    done = orders.fail_and_refund(conn, order_id, reason.strip() or "Отменён администратором", by_admin=admin["id"])
    flash(request, "Заказ отменён, деньги возвращены." if done else "Заказ уже завершён — возврат не сделан.",
          "ok" if done else "error")
    return _back(f"/admin/orders/{order_id}")


@router.post("/orders/{order_id}/complete", dependencies=[Depends(check_csrf)])
def order_complete(order_id: int, request: Request, note: str = Form(""), admin=Depends(admin_user),
                   conn=Depends(get_conn)):
    done = orders.admin_complete(conn, order_id, note)
    flash(request, "Отмечен выполненным." if done else "Заказ уже завершён.", "ok" if done else "error")
    return _back(f"/admin/orders/{order_id}")


@router.post("/orders/{order_id}/recheck", dependencies=[Depends(check_csrf)])
def order_recheck(order_id: int, request: Request, admin=Depends(admin_user), conn=Depends(get_conn)):
    orders.admin_recheck(conn, order_id)
    row = orders.get_order_row(conn, order_id)
    if row and row["status"] == "processing":
        orders.refresh(conn, request.app.state.supplier, row, from_worker=False)
    flash(request, "Статус запрошен у поставщика.")
    return _back(f"/admin/orders/{order_id}")


# ── Каталог ──────────────────────────────────────────────────


@router.get("/products")
def products(request: Request, kind: str = "", q: str = "", admin=Depends(admin_user), conn=Depends(get_conn),
             config: Config = Depends(get_config)):
    items = catalog.list_products(conn, kind=kind if kind in KINDS else "", q=q[:100], include_hidden=True)
    for p in items:
        km = config.kind_markups.get(p["kind"])
        p["prices"] = {t: fmt_unit(apply_markup(to_decimal(p["base_price"]), km if km is not None else m))
                       for t, m in config.markups.items()}
    return render(request, "admin/products.html", {
        "user": admin, "items": items, "kind": kind, "q": q, "kinds": KINDS, "markups": config.markups,
    })


@router.post("/products/{product_id}/toggle", dependencies=[Depends(check_csrf)])
def product_toggle(product_id: str, request: Request, admin=Depends(admin_user), conn=Depends(get_conn)):
    conn.execute("UPDATE products SET hidden = 1 - hidden WHERE id = ?", (product_id,))
    return _back(request.headers.get("referer") or "/admin/products")


# ── Пополнения ───────────────────────────────────────────────


@router.get("/payments")
def payments_list(request: Request, status: str = "pending", admin=Depends(admin_user), conn=Depends(get_conn)):
    where, args = "1=1", []
    if status in ("pending", "paid", "rejected", "cancelled"):
        where += " AND p.status = ?"
        args.append(status)
    rows = conn.execute(
        f"SELECT p.*, u.login, u.balance_micro FROM payments p JOIN users u ON u.id = p.user_id WHERE {where} "
        f"ORDER BY p.id DESC LIMIT 200", args).fetchall()
    return render(request, "admin/payments.html", {
        "user": admin, "rows": rows, "status": status, "titles": {k: v[0] for k, v in PAY_METHODS.items()},
    })


@router.get("/pay-settings")
def pay_settings(request: Request, admin=Depends(admin_user), conn=Depends(get_conn),
                 config: Config = Depends(get_config)):
    from . import payments
    return render(request, "admin/pay_settings.html", {
        "user": admin, "conf": payments.settings(conn, config), "methods": PAY_METHODS,
    })


@router.post("/pay-settings", dependencies=[Depends(check_csrf)])
async def pay_settings_save(request: Request, admin=Depends(admin_user), conn=Depends(get_conn)):
    from . import payments
    form = await request.form()
    details = {code: str(form.get(code, "")) for code in PAY_METHODS}
    try:
        payments.save_settings(conn, details, str(form.get("tjs_rate", "")), str(form.get("min_usd", "")))
    except payments.PaymentError as exc:
        flash(request, str(exc), "error")
    else:
        flash(request, "Реквизиты сохранены — клиенты уже видят их на странице пополнения.")
    return _back("/admin/pay-settings")


@router.post("/payments/{payment_id}/confirm", dependencies=[Depends(check_csrf)])
def payment_confirm(payment_id: int, request: Request, credit: str = Form(""), admin=Depends(admin_user),
                    conn=Depends(get_conn), config: Config = Depends(get_config)):
    from . import payments
    try:
        ok = payments.confirm(conn, config, payment_id, admin["id"], credit.strip() or None)
    except payments.PaymentError as exc:
        flash(request, str(exc), "error")
        return _back("/admin/payments")
    flash(request, "Баланс зачислен, клиент уведомлён." if ok else "Заявка уже обработана.", "ok" if ok else "error")
    return _back("/admin/payments")


@router.post("/payments/{payment_id}/reject", dependencies=[Depends(check_csrf)])
def payment_reject(payment_id: int, request: Request, reason: str = Form(""), admin=Depends(admin_user),
                   conn=Depends(get_conn), config: Config = Depends(get_config)):
    from . import payments
    ok = payments.reject(conn, config, payment_id, admin["id"], reason)
    flash(request, "Заявка отклонена, клиент уведомлён." if ok else "Заявка уже обработана.", "ok" if ok else "error")
    return _back("/admin/payments")


# ── Ошибки ───────────────────────────────────────────────────


@router.get("/errors")
def errors(request: Request, admin=Depends(admin_user), conn=Depends(get_conn)):
    rows = conn.execute(
        "SELECT o.*, u.login FROM orders o JOIN users u ON u.id = o.user_id "
        "WHERE o.status IN ('failed', 'attention') OR (o.status = 'processing' AND o.error IS NOT NULL) "
        "OR o.webhook_state = 'failed' ORDER BY (o.status = 'attention') DESC, o.id DESC LIMIT 200"
    ).fetchall()
    return render(request, "admin/errors.html", {"user": admin, "rows": rows})
