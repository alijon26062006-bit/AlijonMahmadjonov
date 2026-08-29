"""
Общее для страниц админки: проверка входа, страницы ошибок, редиректы.

Вынесено из main.py, чтобы разделы админки могли лежать в отдельных
модулях и не тянуть за собой сам объект приложения.
"""
from fastapi import Request
from fastapi.responses import RedirectResponse, Response

from . import security
from .config import ALLOW_INSECURE, SECURE_COOKIES, SESSION_COOKIE
from .db import connect
from .render import is_secure, no_store, templates


def safe_host(request: Request) -> str:
    """Заголовок Host приходит от клиента: чистим его перед показом."""
    raw = (request.headers.get("host") or "").split(":")[0].lower()
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789.-")
    if raw and 3 <= len(raw) <= 253 and set(raw) <= allowed and "." in raw:
        return raw
    return "ваш-домен"


def insecure_page(request: Request) -> Response:
    """
    По http cookie с флагом Secure браузер не сохраняет, и вход тихо
    ломался бы с невнятным «форма устарела». Говорим прямо: дело
    не в форме, а в том, что пароль по http идёт открытым текстом.
    """
    resp = templates.TemplateResponse(
        request, "admin/insecure.html",
        {"host": safe_host(request)},
        status_code=421,
    )
    return no_store(resp)


def current_session(request: Request):
    with connect() as conn:
        return security.get_session(conn, request.cookies.get(SESSION_COOKIE))


_ERRORS = {
    403: ("Доступ закрыт", "У вас нет прав на эту страницу.", "/admin", "К входу"),
    404: ("Страница не найдена", "Такой страницы нет. Возможно, её удалили "
          "или в адресе опечатка.", "/", "На главную"),
    500: ("Что-то сломалось", "Ошибка на нашей стороне. Мы уже видим её в журнале — "
          "попробуйте ещё раз через минуту.", "/", "На главную"),
}


def error_page(request: Request, code: int) -> Response:
    title, text, back_url, back_label = _ERRORS.get(code, _ERRORS[500])
    return no_store(templates.TemplateResponse(request, "error.html", {
        "code": code, "title": title, "text": text,
        "back_url": back_url, "back_label": back_label,
    }, status_code=code))


def guard(request: Request):
    """Один вход для всех защищённых страниц: (сессия, None) или (None, ответ)."""
    if SECURE_COOKIES and not ALLOW_INSECURE and not is_secure(request):
        return None, insecure_page(request)
    session = current_session(request)
    if session is None:
        return None, no_store(RedirectResponse("/admin", status_code=303))
    return session, None


def back(path: str = "/admin/projects") -> Response:
    return no_store(RedirectResponse(path, status_code=303))


def page(request: Request, session, template: str, **ctx) -> Response:
    """Ответ страницы админки: имя, csrf и запрет кеширования — всегда."""
    data = {"username": session["username"], "csrf": session["csrf_token"]}
    data.update(ctx)
    return no_store(templates.TemplateResponse(request, template, data))
