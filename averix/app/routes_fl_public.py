"""
Публичные страницы площадки: каталог специалистов и карточка.

Всё, что здесь показывается, — настоящие профили настоящих людей,
которые сами попросили публикацию. Ни рейтингов, ни числа выполненных
заказов, ни «отвечает за пять минут» тут нет: этих данных пока
не существует, а рисовать их нельзя.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from . import models, specialists, taxonomy
from .db import connect
from .routes_freelance import context, current, render
from .routes_public import public_notfound

router = APIRouter(prefix="/freelance")


def _int(value: str) -> int | None:
    value = (value or "").strip()
    return int(value) if value.isdigit() else None


def _currency(conn) -> str:
    """Обозначение валюты берётся из настроек, а не пишется в разметке:
    площадка может однажды считать не в сомони."""
    return models.settings(conn, "ru").get("freelance_currency_short") or "смн"


@router.get("/specialists", response_class=HTMLResponse)
async def catalog(request: Request, q: str = "", cat: str = "", level: str = "",
                  busy: str = "", skill: str = "", page: str = "1"):
    session = current(request)
    category_id, skill_id = _int(cat), _int(skill)
    if level not in specialists.LEVELS:
        level = ""
    if busy not in ("available", "partially_busy", "busy"):
        busy = ""

    with connect() as conn:
        result = specialists.public_list(
            conn, q, category_id, level, busy, skill_id, _int(page) or 1)
        facets = specialists.catalog_facets(conn)
        tree = taxonomy.category_tree(conn)
        chosen_skill = taxonomy.get_skill(conn, skill_id) if skill_id else None
        currency = _currency(conn)

    # В фильтре только те направления, где действительно кто-то есть:
    # пустой пункт меню обещает результат, которого нет
    used = facets["categories"]
    for top in tree:
        top["count"] = used.get(top["id"], 0) + sum(
            used.get(child["id"], 0) for child in top["children"])
        top["children"] = [c for c in top["children"] if used.get(c["id"])]
        for child in top["children"]:
            child["count"] = used[child["id"]]
    tree = [t for t in tree if t["count"]]

    ctx = context(request, session, page="specialists",
                  canonical="/freelance/specialists",
                  result=result, tree=tree, facets=facets, currency=currency,
                  people_word=specialists.people_word(facets["total"]),
                  levels=specialists.LEVELS, q=q[:80], cat=cat, level=level,
                  busy=busy, skill=skill, chosen_skill=chosen_skill)
    return render(request, "freelance/specialists.html", ctx)


@router.get("/specialists/{slug}", response_class=HTMLResponse)
async def card(request: Request, slug: str):
    session = current(request)
    with connect() as conn:
        person = specialists.public_one(conn, slug)
        currency = _currency(conn)
    if person is None:
        # Скрытый профиль и несуществующий отвечают одинаково: иначе
        # по ответу можно проверить, есть ли человек на площадке
        return public_notfound(request)
    ctx = context(request, session, page="specialists",
                  canonical=f"/freelance/specialists/{slug}", person=person,
                  currency=currency)
    return render(request, "freelance/specialist.html", ctx)
