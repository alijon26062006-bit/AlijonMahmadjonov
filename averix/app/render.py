"""Общее для публичной части и админки: шаблоны, язык, контекст."""
from fastapi import Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates

from . import models
from .config import BASE_DIR, SITE_URL

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

LANG_COOKIE = "averix-lang"


def no_store(resp: Response) -> Response:
    resp.headers["Cache-Control"] = "no-store"
    return resp


def is_secure(request: Request) -> bool:
    """Схема запроса до nginx: сам прокси ходит к приложению по http."""
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    return proto == "https"


def client_ip(request: Request) -> str:
    """
    За nginx настоящий адрес приходит в X-Forwarded-For. Берём последний
    элемент — его подставляет наш собственный прокси, и подделать его
    клиент не может, в отличие от первого.
    """
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[-1].strip()[:64]
    return (request.client.host if request.client else "?")[:64]


def lang_of(request: Request) -> str:
    """Язык берём из cookie, которую ставит переключатель на сайте."""
    return "tg" if request.cookies.get(LANG_COOKIE) == "tg" else "ru"


def public_context(request: Request, conn, page: str = "", **extra) -> dict:
    """Базовый набор для любой публичной страницы."""
    lang = lang_of(request)
    s = models.settings(conn, lang)
    tg = (s.get("contact_telegram") or "").lstrip("@")
    gh = (s.get("contact_github") or "").strip()
    ctx = {
        "lang": lang,
        "s": s,
        # Показатели считаем один раз здесь: они нужны и главной, и студии
        "stats": models.visible_stats(s),
        "page": page,
        "site_url": SITE_URL,
        "canonical": request.url.path,
        "server_i18n": True,
        "tg_url": f"https://t.me/{tg}" if tg else "#",
        "gh_url": f"https://github.com/{gh}" if gh else "",
        "request_types": models.REQUEST_TYPES,
        "categories": models.CATEGORIES,
        "old": {},
        "errors": {},
    }
    ctx.update(extra)
    return ctx
