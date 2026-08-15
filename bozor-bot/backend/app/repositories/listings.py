"""Каталог: динамические фильтры из схемы + keyset-пагинация.

Ключи фильтров принимаются ТОЛЬКО из схемы категории (белый список) —
произвольные параметры запроса не могут попасть в SQL.
"""
import base64
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import Numeric, and_, cast, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import ST_APPROVED, Listing
from app.schemas_engine.fields import CategorySchema

PAGE_MAX = 50


def encode_cursor(published_at: datetime, listing_id: int) -> str:
    raw = f"{published_at.isoformat()}|{listing_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, int] | None:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        ts, _, lid = raw.partition("|")
        return datetime.fromisoformat(ts), int(lid)
    except Exception:
        return None


def _num(value: str) -> Decimal | None:
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return None


def build_conditions(schema: CategorySchema | None, params: dict) -> list:
    """Условия WHERE из параметров запроса, строго по схеме."""
    conds = [Listing.status == ST_APPROVED]

    if schema:
        conds.append(Listing.category_slug == schema.slug)

    if (city := params.get("city_id")) and str(city).isdigit():
        conds.append(Listing.city_id == int(city))
    if (district := params.get("district_id")):
        ids = [int(x) for x in str(district).split(",") if x.isdigit()]
        if ids:
            conds.append(Listing.district_id.in_(ids))
    if (v := _num(params.get("price_min", ""))) is not None:
        conds.append(Listing.price_usd >= v)
    if (v := _num(params.get("price_max", ""))) is not None:
        conds.append(Listing.price_usd <= v)
    if (q := params.get("q", "").strip()):
        like = f"%{q[:80]}%"
        conds.append(or_(Listing.title.ilike(like), Listing.description.ilike(like)))
    if all(k in params for k in ("min_lon", "min_lat", "max_lon", "max_lat")):
        try:
            conds += [Listing.lon.between(float(params["min_lon"]), float(params["max_lon"])),
                      Listing.lat.between(float(params["min_lat"]), float(params["max_lat"]))]
        except ValueError:
            pass

    if not schema:
        return conds

    for spec in schema.filterable():
        if spec.key in ("price", "city_id", "district_id"):
            continue                      # физические колонки обработаны выше
        expr = Listing.attrs[spec.key].astext
        if spec.filter in ("multiselect", "exact"):
            raw = params.get(spec.key)
            if raw:
                vals = [v for v in str(raw).split(",") if v][:20]
                if vals:
                    conds.append(expr.in_(vals))
        elif spec.filter == "checkbox":
            if str(params.get(spec.key, "")).lower() in ("1", "true", "yes"):
                conds.append(expr == "true")
        elif spec.filter == "range":
            lo = _num(params.get(f"{spec.key}_min", ""))
            hi = _num(params.get(f"{spec.key}_max", ""))
            if lo is not None or hi is not None:
                num = cast(expr, Numeric)
                if lo is not None:
                    conds.append(and_(expr.isnot(None), num >= lo))
                if hi is not None:
                    conds.append(and_(expr.isnot(None), num <= hi))
    return conds


async def catalog_page(session: AsyncSession, schema: CategorySchema | None,
                       params: dict) -> tuple[list[Listing], str | None]:
    limit = min(int(params.get("limit", 20) or 20), PAGE_MAX)
    conds = build_conditions(schema, params)

    stmt = (select(Listing).where(*conds)
            .options(selectinload(Listing.photos))
            .order_by(Listing.published_at.desc(), Listing.id.desc())
            .limit(limit + 1))

    sort = params.get("sort", "newest")
    if sort in ("price_asc", "price_desc"):
        order = Listing.price_usd.asc() if sort == "price_asc" else Listing.price_usd.desc()
        stmt = (select(Listing).where(*conds)
                .options(selectinload(Listing.photos))
                .order_by(order, Listing.id.desc()).limit(limit + 1))
        offset = int(params.get("offset", 0) or 0)      # для ценовой сортировки — offset
        stmt = stmt.offset(min(offset, 2000))
        rows = (await session.scalars(stmt)).all()
        return rows[:limit], (str(offset + limit) if len(rows) > limit else None)

    if (cursor := params.get("cursor")):
        decoded = decode_cursor(cursor)
        if decoded:
            stmt = stmt.where(
                tuple_(Listing.published_at, Listing.id) < (decoded[0], decoded[1]))

    rows = (await session.scalars(stmt)).all()
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor(last.published_at, last.id)
    return rows[:limit], next_cursor
