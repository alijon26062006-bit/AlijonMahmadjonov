"""Общие зависимости FastAPI: база, текущий пользователь, CSRF, шаблоны."""

from __future__ import annotations

import json
import secrets
import sqlite3
from typing import Any, Iterator

from fastapi import Request
from fastapi.templating import Jinja2Templates

from . import accounts, db
from .config import ROOT, Config
from .money import fmt, fmt_unit
from .suppliers import KIND_TITLES

templates = Jinja2Templates(directory=str(ROOT / "templates"))
templates.env.globals.update(fmt=fmt, fmt_unit=fmt_unit, kind_titles=KIND_TITLES)
templates.env.filters["fromjson"] = json.loads
templates.env.filters["faq_item"] = lambda qa: {
    "@type": "Question", "name": qa[0], "acceptedAnswer": {"@type": "Answer", "text": qa[1]}}


def _img(url):
    from .catalog_job import local_url
    return local_url(url)


templates.env.filters["img"] = _img


def _price(value, unit: str = "item") -> str:
    """Цена для витрины: у звёзд — как есть (доли цента), у остального — 4 знака, округление вверх,
    как при списании."""
    from decimal import ROUND_CEILING, Decimal
    d = Decimal(str(value))
    return str(d) if unit == "star" else str(d.quantize(Decimal("0.0001"), rounding=ROUND_CEILING))


templates.env.filters["price"] = _price


def _asset_version() -> str:
    """Метка версии стилей: меняется с файлом, и браузер не держит старый CSS из кеша."""
    import hashlib

    h = hashlib.sha1()
    for name in ("donatix.css", "code.js", "logo.svg"):
        path = ROOT / "static" / name
        if path.exists():
            h.update(path.read_bytes())
    return h.hexdigest()[:10]


templates.env.globals["asset_v"] = _asset_version()

STATUS_TITLES = {
    "processing": "В обработке",
    "completed": "Выполнен",
    "failed": "Отменён, деньги возвращены",
    "attention": "Требует внимания",
    "pending": "Ждёт одобрения",
    "active": "Активен",
    "blocked": "Заблокирован",
}
templates.env.globals["status_titles"] = STATUS_TITLES


class LoginRequired(Exception):
    pass


class Forbidden(Exception):
    pass


def get_config(request: Request) -> Config:
    return request.app.state.config


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    conn = db.connect(request.app.state.config.db_path)
    try:
        yield conn
    finally:
        conn.close()


def session_user(request: Request, conn: sqlite3.Connection) -> sqlite3.Row | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = accounts.get_user(conn, int(user_id))
    if user is None or user["status"] == "blocked":
        request.session.clear()
        return None
    return user


def csrf_token(request: Request) -> str:
    token = request.session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(24)
        request.session["csrf"] = token
    return token


async def check_csrf(request: Request) -> None:
    form = await request.form()
    sent = str(form.get("csrf", ""))
    expected = request.session.get("csrf", "")
    if not expected or not secrets.compare_digest(sent, expected):
        raise Forbidden("Форма устарела. Обновите страницу и попробуйте ещё раз.")


def flash(request: Request, message: str, kind: str = "ok") -> None:
    request.session.setdefault("flash", []).append({"kind": kind, "text": message})


#: Страницы для поисковиков (они же в sitemap.xml)
INDEXABLE = {"/": ("daily", "1.0"), "/docs": ("weekly", "0.8"), "/register": ("monthly", "0.5"),
              "/privacy": ("yearly", "0.2"), "/terms": ("yearly", "0.2")}


def render(request: Request, name: str, ctx: dict[str, Any] | None = None, status_code: int = 200):
    ctx = dict(ctx or {})
    config: Config = request.app.state.config
    ctx.setdefault("user", None)
    ctx["site_name"] = config.site_name
    ctx["support_contact"] = config.support_contact
    ctx["csrf"] = csrf_token(request)
    ctx["flashes"] = request.session.pop("flash", [])
    ctx["path"] = request.url.path
    ctx["base_url"] = config.base_url
    ctx["google_verify"] = config.google_verify
    ctx["yandex_verify"] = config.yandex_verify
    ctx["google_login"] = bool(config.google_client_id and config.google_client_secret)
    ctx["canonical"] = config.base_url + request.url.path
    # В поиск попадают только публичные страницы; кабинет, админка и ошибки — нет
    ctx["noindex"] = status_code >= 400 or request.url.path not in INDEXABLE
    ctx["unread"] = 0
    ctx["low_balance_micro"] = 0
    if ctx.get("user") is not None:
        from .notify import unread_count
        c = db.connect(config.db_path)
        try:
            ctx["unread"] = unread_count(c, ctx["user"]["id"])
            low = db.get_setting(c, "pay.low_balance_usd") or str(config.low_balance_usd)
            ctx["low_balance_micro"] = int(float(low) * 10_000)
        finally:
            c.close()
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)
