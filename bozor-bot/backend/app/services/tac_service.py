"""Определение модели телефона по IMEI — без обращения в сеть.

Первые 8 цифр IMEI (TAC) выдаются производителю на конкретную модель, поэтому
у всех Redmi Note 12 одной партии они совпадают. Официальный реестр GSMA
платный и выдаётся операторам по договору, зато таблицу можно собрать самим:

  1. Импортом открытого списка TAC — `python -m app.seed.import_tac файл.csv`.
  2. Наблюдением: модератор одобрил объявление, где рядом стоят IMEI и модель —
     значит пара верна. Две сошедшиеся записи, и подсказка начинает работать.

Второй путь точнее для Таджикистана: таблица наполняется теми аппаратами,
которые здесь действительно продают, а не теми, что попали в чужой список.
"""
import re

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import TacModel


def tac_of(imei: str | None) -> str | None:
    digits = re.sub(r"\D", "", imei or "")
    return digits[:8] if len(digits) >= 8 else None


def _tidy(value: str | None, limit: int) -> str | None:
    v = re.sub(r"\s+", " ", (value or "")).strip()
    return v[:limit] if v else None


async def lookup(session: AsyncSession, imei: str | None) -> dict | None:
    """{'brand', 'model'} либо None, если такой аппарат ещё не встречался."""
    tac = tac_of(imei)
    if not tac:
        return None
    row = await session.get(TacModel, tac)
    if not row:
        return None
    # Импортированному списку верим сразу, своим наблюдениям — с двух совпадений
    if row.source == "learned" and \
            row.confirmations < get_settings().tac_min_confirmations:
        return None
    return {"brand": row.brand, "model": row.model,
            "source": row.source, "confirmations": row.confirmations}


async def resolve_brand(session: AsyncSession, raw) -> str | None:
    """Бренд в объявлении хранится названием («Samsung»), а не номером —
    справочник отдаёт варианты парой имя/имя. Остаётся привести к порядку.

    Функция асинхронная намеренно: если справочник когда-нибудь перейдёт на
    идентификаторы, сюда добавится запрос, а вызовы менять не придётся.
    """
    if raw in (None, "", []):
        return None
    return _tidy(str(raw), 60)


async def learn(session: AsyncSession, imei: str | None,
                brand: str | None, model: str | None) -> None:
    """Запомнить пару из одобренного объявления.

    Совпало с тем, что уже знаем — счётчик растёт. Разошлось — счётчик
    сбрасывается на новую пару: свежие объявления вернее старой опечатки.
    Импортированную запись не трогаем: список надёжнее одного продавца.
    """
    tac = tac_of(imei)
    brand = _tidy(brand, 60)
    model = _tidy(model, 120)
    if not tac or not brand or not model:
        return

    existing = await session.get(TacModel, tac)
    if existing and existing.source == "import":
        return
    if existing and existing.brand.lower() == brand.lower() \
            and existing.model.lower() == model.lower():
        existing.confirmations += 1
        await session.commit()
        return

    stmt = pg_insert(TacModel).values(
        tac=tac, brand=brand, model=model, source="learned", confirmations=1)
    await session.execute(stmt.on_conflict_do_update(
        index_elements=[TacModel.tac],
        set_={"brand": brand, "model": model, "confirmations": 1},
        where=TacModel.source != "import"))
    await session.commit()


async def stats(session: AsyncSession) -> dict:
    """Для админ-панели: насколько справочник вырос."""
    rows = (await session.execute(
        select(TacModel.source, TacModel.confirmations))).all()
    return {
        "total": len(rows),
        "imported": sum(1 for s, _ in rows if s == "import"),
        "learned_active": sum(1 for s, c in rows
                              if s == "learned"
                              and c >= get_settings().tac_min_confirmations),
    }
