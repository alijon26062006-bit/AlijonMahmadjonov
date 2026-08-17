"""Идемпотентная загрузка справочников: города, марки, курс валют."""
import asyncio
import json
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.db.base import SessionMaker
from app.db.models import Brand, City, CurrencyRate

DATA = Path(__file__).parent / "data"


def _load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


async def seed() -> None:
    s = get_settings()
    async with SessionMaker() as session:
        existing = {c.name for c in (await session.scalars(select(City))).all()}
        for i, c in enumerate(_load("cities.json")["cities"]):
            if c["name"] in existing:
                continue
            session.add(City(name=c["name"], delivery_days=c["delivery_days"],
                             sort_order=i))
        await session.commit()

        existing = {b.name for b in (await session.scalars(select(Brand))).all()}
        for b in _load("brands.json")["brands"]:
            if b["name"] in existing:
                continue
            session.add(Brand(name=b["name"], areas=b["areas"],
                              sort_order=b["sort_order"]))
        await session.commit()

        for code, per_usd in (("USD", 1), (s.currency, s.kzt_per_usd)):
            if not await session.get(CurrencyRate, code):
                session.add(CurrencyRate(code=code, per_usd=Decimal(str(per_usd))))
        await session.commit()

    print("Справочники загружены")


if __name__ == "__main__":
    asyncio.run(seed())
