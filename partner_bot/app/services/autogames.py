"""Все игры поставщика — в меню бота одним действием.

Нужен боту из конструктора Donatix: владелец не должен искать и добавлять
игры по одной — они приходят сразу, со всеми регионами, и включаются,
если задан курс доллара (иначе цену посчитать не из чего).
"""
from __future__ import annotations

import logging

import aiosqlite

from app import db, runtime

log = logging.getLogger(__name__)

# Русские названия игр, как их пишут владельцы, → как пишет поставщик
ALIASES = {
    "фри фаер": "free fire", "фрифаер": "free fire", "фри фаир": "free fire", "фф": "free fire",
    "пабг": "pubg", "пубг": "pubg", "пабджи": "pubg", "пубджи": "pubg",
    "млбб": "mobile legends", "мобла": "mobile legends", "мобайл легенд": "mobile legends",
    "мобайл": "mobile", "легенд": "legends",
    "стендофф": "standoff", "стандофф": "standoff", "геншин": "genshin", "бравл": "brawl",
    "клеш": "clash", "клэш": "clash", "роблокс": "roblox", "фортнайт": "fortnite",
    "калл оф дьюти": "call of duty", "кал оф дьюти": "call of duty", "кодм": "call of duty",
    "хонкай": "honkai", "валорант": "valorant", "стим": "steam",
}


def expand(query: str) -> str:
    q = query.lower()
    for ru, en in sorted(ALIASES.items(), key=lambda kv: -len(kv[0])):
        q = q.replace(ru, en)
    return q


def matches(words: list[str], haystack: str) -> bool:
    """Слово найдено целиком или, для длинных, по основе («индонезии» → «индонез»)."""
    for w in words:
        if w in haystack:
            continue
        if len(w) >= 6 and w[: len(w) - 2] in haystack:
            continue
        return False
    return True


async def import_all(conn: aiosqlite.Connection, catalog: list[dict]) -> tuple[int, int]:
    """Добавить все категории каталога. Возвращает (добавлено новых, включено)."""
    from app.services import regions as reg

    have = {g.category_id: g for g in await db.list_games(conn)}
    added = enabled = 0
    for item in catalog:
        code = item["category_id"]
        names = [str(spec.get("name") if isinstance(spec, dict) else spec)
                 for spec in item.get("fields") or []
                 if (spec.get("name") if isinstance(spec, dict) else spec)]
        if code not in have:
            await db.add_game(conn, category_id=code, title=item.get("name") or code,
                              field=",".join(names) or "user_id",
                              region=reg.nick_region(code, item.get("name", "")))
            added += 1
        game = await db.get_game(conn, code)
        if game is not None and not game.enabled and runtime.usd_rate() > 0 and code not in have:
            await db.update_game(conn, code, enabled=1)
            enabled += 1
    await db.load_game_titles(conn)
    return added, enabled
