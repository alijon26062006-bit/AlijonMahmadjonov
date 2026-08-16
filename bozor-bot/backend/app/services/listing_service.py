"""Создание объявления из данных мастера / веб-формы и смена статусов."""
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import (
    ST_APPROVED, ST_PENDING, BlacklistEntry, CurrencyRate, Listing,
    ListingPhoto, User,
)
from app.schemas_engine.fields import CategorySchema
from app.schemas_engine.registry import option_label, render_title
from app.services import identifiers, tac_service, vin_decoder

COLUMN_KEYS = {"price", "city_id", "district_id", "address", "description",
               "contact_mode", "is_negotiable"}


class LimitExceeded(Exception):
    pass


async def to_usd(session: AsyncSession, amount: Decimal, currency: str) -> Decimal:
    rate = await session.get(CurrencyRate, currency)
    per_usd = rate.per_usd if rate else Decimal("1")
    return (amount / per_usd).quantize(Decimal("0.01"))


async def check_limits(session: AsyncSession, user: User) -> None:
    s = get_settings()
    day_ago = datetime.utcnow() - timedelta(days=1)
    daily = await session.scalar(
        select(func.count()).select_from(Listing)
        .where(Listing.author_id == user.id, Listing.created_at > day_ago))
    if daily >= s.daily_listing_limit:
        raise LimitExceeded(f"Не более {s.daily_listing_limit} объявлений в сутки")
    active = await session.scalar(
        select(func.count()).select_from(Listing)
        .where(Listing.author_id == user.id,
               Listing.status.in_((ST_PENDING, ST_APPROVED))))
    if active >= s.active_listing_limit:
        raise LimitExceeded(f"Не более {s.active_listing_limit} активных объявлений")


async def _flag_checks(session: AsyncSession, schema: CategorySchema,
                       values: dict) -> str | None:
    """Проверки для модератора: чёрный список, повтор идентификатора."""
    notes = []
    for spec in schema.fields:
        if spec.type != "identifier" or not values.get(spec.key):
            continue
        val = str(values[spec.key])
        kind = "imei" if spec.identifier == "imei" else \
               "vin" if "vin" in (spec.identifier or "") else "serial"
        bl = await session.scalar(
            select(BlacklistEntry).where(BlacklistEntry.kind == kind,
                                         BlacklistEntry.value_norm == val))
        if bl:
            notes.append(f"⛔️ {spec.label} найден в чёрном списке площадки")
        dup = await session.scalar(
            select(Listing.id).where(
                Listing.attrs[spec.key].astext == val,
                Listing.status.in_((ST_PENDING, ST_APPROVED))).limit(1))
        if dup:
            notes.append(f"⚠️ {spec.label} уже встречается в объявлении #{dup}")

        # Номер знает о вещи больше, чем написал продавец. Расходятся —
        # решает модератор: бывает и честная ошибка, и подмена.
        if kind == "vin":
            info = await vin_decoder.decode(val)
            declared_brand = await tac_service.resolve_brand(session, values.get("brand"))
            for diff in vin_decoder.mismatch(info, declared_brand, values.get("year")):
                notes.append(f"⚠️ Не сходится с базой по VIN — {diff}")
        elif kind == "imei":
            known = await tac_service.lookup(session, val)
            declared = str(values.get("model") or "").strip().lower()
            if known and declared and known["model"].lower() not in declared \
                    and declared not in known["model"].lower():
                notes.append(f'⚠️ По IMEI это «{known["brand"]} {known["model"]}», '
                             f'а указана модель «{values.get("model")}»')
    return "\n".join(notes) or None


async def create_listing(session: AsyncSession, user: User, schema: CategorySchema,
                         values: dict, photos: list[dict]) -> Listing:
    """values — ключ поля → значение; photos — [{file_id, thumb_file_id, file_unique_id, ...}]."""
    await check_limits(session, user)

    labels = {f.key: option_label(f, values.get(f.key))
              for f in schema.fields if values.get(f.key) is not None}
    price = Decimal(str(values.get("price", 0)))
    currency = str(values.get("currency", "TJS"))

    listing = Listing(
        author_id=user.id,
        category_slug=schema.slug,
        title=render_title(schema, values, labels),
        description=str(values.get("description", ""))[:1000],
        price=price,
        currency=currency,
        price_usd=await to_usd(session, price, currency),
        is_negotiable=bool(values.get("is_negotiable")),
        city_id=int(values["city_id"]) if values.get("city_id") else None,
        district_id=int(values["district_id"]) if values.get("district_id") else None,
        address=values.get("address"),
        lat=values.get("lat"), lon=values.get("lon"),
        contact_mode=str(values.get("contact_mode", "telegram")),
        contact_phone=values.get("contact_phone") or user.phone,
        contact_username=user.username,
        status=ST_PENDING,
        attrs={k: v for k, v in values.items()
               if k not in COLUMN_KEYS
               and k not in ("currency", "lat", "lon", "contact_phone", "photos")
               and not k.startswith("_")},
    )
    listing.flag_note = await _flag_checks(session, schema, values)
    session.add(listing)
    await session.flush()

    for i, p in enumerate(photos[: get_settings().max_photos]):
        session.add(ListingPhoto(
            listing_id=listing.id, file_id=p["file_id"],
            thumb_file_id=p.get("thumb_file_id"),
            # с сайта приходит вместе с фото — берём только целое число
            thumb_w=p["thumb_w"] if isinstance(p.get("thumb_w"), int) else None,
            file_unique_id=p["file_unique_id"],
            width=p.get("width"), height=p.get("height"), position=i))
    await session.commit()
    await session.refresh(listing)
    return listing


def normalize_identifier(spec_identifier: str, raw: str):
    return identifiers.validate(spec_identifier, raw)
