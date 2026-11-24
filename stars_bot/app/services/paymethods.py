"""Свои реквизиты: любой банк и номер, их владелец добавляет в панели.

Кнопки пополнения рисуются без обращения к базе, поэтому список держим
в памяти и перечитываем после каждой правки в панели.
"""
from __future__ import annotations

import aiosqlite

from app import db

_methods: list[dict] = []


async def load(conn: aiosqlite.Connection) -> None:
    _methods[:] = await db.list_pay_methods(conn)


def all_() -> list[dict]:
    return list(_methods)


def enabled() -> list[dict]:
    return [m for m in _methods if m.get("enabled")]


def get(method_id) -> dict | None:
    try:
        method_id = int(method_id)
    except (TypeError, ValueError):
        return None
    return next((m for m in _methods if m["id"] == method_id), None)
