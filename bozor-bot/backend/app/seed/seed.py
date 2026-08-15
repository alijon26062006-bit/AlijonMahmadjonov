"""Идемпотентная загрузка справочников: города, бренды, модели, курс валют."""
import asyncio
import json
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.db.base import SessionMaker
from app.db.models import Brand, City, CurrencyRate, District, VehicleModel

DATA = Path(__file__).parent / "data"


def _load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


async def seed() -> None:
    s = get_settings()
    async with SessionMaker() as session:
        # Города и районы
        existing = {c.name for c in (await session.scalars(select(City))).all()}
        for i, c in enumerate(_load("cities.json")["cities"]):
            if c["name"] in existing:
                continue
            city = City(name=c["name"], lat=c["lat"], lon=c["lon"], sort_order=i)
            session.add(city)
            await session.flush()
            for d in c["districts"]:
                session.add(District(city_id=city.id, name=d))
        await session.commit()

        # Бренды
        existing = {b.name for b in (await session.scalars(select(Brand))).all()}
        for b in _load("brands.json")["brands"]:
            if b["name"] in existing:
                continue
            session.add(Brand(name=b["name"], areas=b["areas"],
                              popular=b["popular"], sort_order=b["sort_order"]))
        await session.commit()

        # Модели автомобилей
        brands = {b.name: b.id for b in (await session.scalars(select(Brand))).all()}
        have = {(m.brand_id, m.name) for m in (await session.scalars(select(VehicleModel))).all()}
        for m in _load("car_models.json")["models"]:
            bid = brands.get(m["brand"])
            if not bid or (bid, m["name"]) in have:
                continue
            session.add(VehicleModel(brand_id=bid, name=m["name"],
                                     area=m["area"], sort_order=m["sort_order"]))
        await session.commit()

        # Курсы валют
        for code, per_usd in (("USD", 1), ("TJS", s.tjs_per_usd)):
            if not await session.get(CurrencyRate, code):
                session.add(CurrencyRate(code=code, per_usd=Decimal(str(per_usd))))
        await session.commit()

    print("Справочники загружены")


if __name__ == "__main__":
    asyncio.run(seed())
