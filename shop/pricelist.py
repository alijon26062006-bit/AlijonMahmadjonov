"""Рӯйхати нархҳо барои соҳибони калиди API ва шарикони конструктор.

Нарх аз нархи харид худкор ҳисоб мешавад ва ҳамеша ҳамон аст, ки ҳангоми
харид гирифта мешавад:

    API     = нархи харид × курс × (1 + наценкаи API)
    яклухт  = нархи харид × курс × (1 + наценкаи конструктор)
"""

from __future__ import annotations

from dataclasses import dataclass

from . import catalog, costs, wholesale
from .db import Database

#: Паёми Telegram то 4096 аломат — бо захира барои HTML ва сарлавҳа.
CHUNK = 3500


@dataclass(frozen=True)
class Viewer:
    """Кадом нархҳоро нишон диҳем."""

    api: bool = False          # калиди API дорад
    wholesale: bool = False    # шарики конструктор

    @property
    def any(self) -> bool:
        return self.api or self.wholesale


def viewer_of(db: Database, user_id: int, *, is_admin: bool = False) -> Viewer:
    if is_admin:
        return Viewer(api=True, wholesale=True)
    return Viewer(
        api=db.active_api_key(user_id) is not None,
        wholesale=db.constructor_access(user_id) is not None or bool(db.tenants(user_id)),
    )


@dataclass(frozen=True)
class Item:
    code: str
    title: str
    group: str
    api: int | None
    wholesale: int | None


def items(db: Database, category: str, viewer: Viewer) -> list[Item]:
    """Молҳои фурӯхташавандаи бахш бо нархҳои ҳамин корбар."""
    rate, api_markup = costs.usd_rate(db), costs.api_markup(db)
    groups = {g["code"]: g["title"] for g in db.groups(category, only_active=False)}
    out = []
    for row in db.products(category):
        api = costs.api_price(row["cost"], rate, api_markup) if viewer.api else None
        whole = wholesale.wholesale_price(db, row) if viewer.wholesale else None
        if api is None and whole is None:
            continue                        # нархи харид нест — намефурӯшем
        out.append(Item(row["code"], row["title"], groups.get(row["group_code"] or "", ""),
                        api, whole))
    return out


def categories(db: Database, viewer: Viewer) -> list[tuple[str, int]]:
    """(бахш, шумораи мол) — танҳо бахшҳое, ки моли нархдор доранд."""
    found = []
    for category in catalog.CATEGORIES:
        count = len(items(db, category, viewer))
        if count:
            found.append((category, count))
    return found


def chunks(lines: list[str], limit: int = CHUNK) -> list[str]:
    """Сатрҳоро ба паёмҳои то ``limit`` аломат тақсим мекунад."""
    out, current = [], ""
    for line in lines:
        if current and len(current) + len(line) + 1 > limit:
            out.append(current)
            current = ""
        current = f"{current}\n{line}" if current else line
    if current:
        out.append(current)
    return out
