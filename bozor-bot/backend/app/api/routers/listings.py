"""Каталог, карточка, мои объявления, подача с сайта, контакты, жалобы."""
import hashlib
import hmac
import uuid as uuid_mod

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.api.deps import Cache, CurrentUser, Db, OptionalUser
from app.config import get_settings
from app.db.models import (
    ST_APPROVED, ST_ARCHIVED, ST_OCCUPIED, ST_REJECTED, ST_SOLD,
    City, District, Favorite, Listing, Report, User,
)
from app.repositories.listings import catalog_page
from app.schemas_engine.registry import get_schema, option_label
from app.services import feed_service, listing_service

router = APIRouter(prefix="/api/listings", tags=["listings"])


async def _names(session, listings: list[Listing]) -> tuple[dict, dict]:
    city_ids = {l.city_id for l in listings if l.city_id}
    district_ids = {l.district_id for l in listings if l.district_id}
    cities = {c.id: c.name for c in (await session.scalars(
        select(City).where(City.id.in_(city_ids)))).all()} if city_ids else {}
    districts = {d.id: d.name for d in (await session.scalars(
        select(District).where(District.id.in_(district_ids)))).all()} if district_ids else {}
    return cities, districts


def _photo_urls(listing: Listing) -> list[dict]:
    return [{"thumb": f"/api/photos/{p.public_id}?size=thumb",
             "full": f"/api/photos/{p.public_id}",
             "width": p.width, "height": p.height}
            for p in listing.photos]


def _card(listing: Listing, cities: dict, districts: dict) -> dict:
    return {
        "public_id": str(listing.public_id),
        "category": listing.category_slug,
        "title": listing.title,
        "price": float(listing.price),
        "currency": listing.currency,
        "is_negotiable": listing.is_negotiable,
        "city": cities.get(listing.city_id),
        "district": districts.get(listing.district_id),
        "status": listing.status,
        "published_at": listing.published_at.isoformat() if listing.published_at else None,
        "photos": _photo_urls(listing)[:1],
        "lat": listing.lat, "lon": listing.lon,
    }


def _specs(listing: Listing) -> list[dict]:
    schema = get_schema(listing.category_slug)
    if not schema:
        return []
    out = []
    for spec in schema.fields:
        if spec.stored != "attrs" or spec.type in ("photos", "geo"):
            continue
        val = listing.attrs.get(spec.key)
        if val in (None, "", [], False):
            continue
        out.append({"key": spec.key, "label": spec.label,
                    "value": option_label(spec, val),
                    "unit": spec.unit,
                    "verified": spec.type == "identifier"})
    return out


@router.get("")
async def catalog(request: Request, session: Db):
    params = dict(request.query_params)
    schema = get_schema(params.get("category", "")) if params.get("category") else None
    rows, next_cursor = await catalog_page(session, schema, params)
    cities, districts = await _names(session, rows)
    return {"items": [_card(l, cities, districts) for l in rows],
            "next_cursor": next_cursor}


@router.get("/my")
async def my_listings(session: Db, user: CurrentUser):
    rows = (await session.scalars(
        select(Listing).where(Listing.author_id == user.id)
        .options(selectinload(Listing.photos))
        .order_by(Listing.created_at.desc()).limit(50))).all()
    cities, districts = await _names(session, rows)
    out = []
    for l in rows:
        card = _card(l, cities, districts)
        card["reject_reason"] = l.reject_reason
        card["is_rent"] = bool(get_schema(l.category_slug) and
                               get_schema(l.category_slug).is_rent)
        out.append(card)
    return {"items": out}


@router.get("/{public_id}")
async def detail(public_id: uuid_mod.UUID, session: Db, viewer: OptionalUser):
    listing = (await session.scalars(
        select(Listing).where(Listing.public_id == public_id)
        .options(selectinload(Listing.photos)))).first()
    if not listing:
        raise HTTPException(404, "not_found")
    is_owner = viewer and viewer.id == listing.author_id
    if listing.status != ST_APPROVED and not is_owner and not (viewer and viewer.is_admin):
        raise HTTPException(404, "not_found")

    cities, districts = await _names(session, [listing])
    await session.execute(update(Listing).where(Listing.id == listing.id)
                          .values(views_count=Listing.views_count + 1))
    await session.commit()
    # Событие для алгоритма ленты — собираем с первого дня
    if listing.status == ST_APPROVED:
        await feed_service.log_event(session, listing.id,
                                     viewer.id if viewer else None, "view")

    card = _card(listing, cities, districts)
    card.update({
        "description": listing.description,
        "photos": _photo_urls(listing),
        "specs": _specs(listing),
        "views_count": listing.views_count + 1,
        "address": listing.address,
        "is_owner": bool(is_owner),
    })
    return card


@router.post("/{public_id}/contact")
async def contact(public_id: uuid_mod.UUID, session: Db, user: CurrentUser):
    listing = await session.scalar(
        select(Listing).where(Listing.public_id == public_id,
                              Listing.status == ST_APPROVED))
    if not listing:
        raise HTTPException(404, "not_found")
    await session.execute(update(Listing).where(Listing.id == listing.id)
                          .values(contacts_count=Listing.contacts_count + 1))
    await session.commit()
    await feed_service.log_event(session, listing.id, user.id, "contact_click")
    out = {"contact_mode": listing.contact_mode}
    if listing.contact_mode in ("telegram", "both") and listing.contact_username:
        out["telegram"] = f"https://t.me/{listing.contact_username}"
    if listing.contact_mode in ("phone", "both") and listing.contact_phone:
        out["phone"] = listing.contact_phone
    return out


class StatusPatch(BaseModel):
    status: str


OWNER_STATUSES = {ST_SOLD, ST_ARCHIVED, ST_OCCUPIED, ST_APPROVED}


@router.patch("/{public_id}")
async def patch_status(public_id: uuid_mod.UUID, body: StatusPatch,
                       session: Db, user: CurrentUser):
    listing = await session.scalar(
        select(Listing).where(Listing.public_id == public_id))
    if not listing or listing.author_id != user.id:
        raise HTTPException(404, "not_found")
    if body.status not in OWNER_STATUSES:
        raise HTTPException(400, "bad_status")
    if body.status == ST_APPROVED and listing.status not in (ST_OCCUPIED, ST_SOLD, ST_ARCHIVED):
        raise HTTPException(400, "bad_transition")
    listing.status = body.status
    await session.commit()
    return {"status": listing.status}


class ReportIn(BaseModel):
    reason: str
    comment: str | None = None


@router.post("/{public_id}/report")
async def report(public_id: uuid_mod.UUID, body: ReportIn,
                 session: Db, user: CurrentUser):
    listing = await session.scalar(
        select(Listing).where(Listing.public_id == public_id))
    if not listing:
        raise HTTPException(404, "not_found")
    exists = await session.scalar(
        select(Report).where(Report.listing_id == listing.id,
                             Report.reporter_id == user.id))
    if exists:
        raise HTTPException(409, "already_reported")
    session.add(Report(listing_id=listing.id, reporter_id=user.id,
                       reason=body.reason[:20], comment=(body.comment or "")[:500]))
    await session.commit()
    return {"ok": True}


# ─────────────────── Подача с сайта ───────────────────

def sign_photo(p: dict) -> str:
    msg = f'{p["file_id"]}|{p["file_unique_id"]}'.encode()
    return hmac.new(get_settings().jwt_secret.encode(), msg, hashlib.sha256).hexdigest()


class WebSubmission(BaseModel):
    category: str
    values: dict
    photos: list[dict]      # из /api/uploads/photo, с подписью sig


@router.post("")
async def create_from_web(body: WebSubmission, session: Db, user: CurrentUser):
    schema = get_schema(body.category)
    if not schema:
        raise HTTPException(400, "bad_category")

    photos = []
    for p in body.photos[: get_settings().max_photos]:
        if p.get("sig") != sign_photo(p):        # фото только из нашей загрузки
            raise HTTPException(400, "bad_photo_signature")
        photos.append(p)
    if not photos:
        raise HTTPException(400, "photos_required")

    values = dict(body.values)
    # серверная валидация обязательных полей по схеме
    for spec in schema.fields:
        if spec.type in ("photos", "geo"):
            continue
        if spec.required and schema.visible(spec, values) and \
                values.get(spec.key) in (None, "", []):
            raise HTTPException(400, f"required:{spec.key}")
        if spec.type == "identifier" and values.get(spec.key):
            ok, normalized, err, _ = listing_service.normalize_identifier(
                spec.identifier or "serial", str(values[spec.key]))
            if not ok:
                raise HTTPException(400, f"invalid:{spec.key}")
            values[spec.key] = normalized

    try:
        listing = await listing_service.create_listing(
            session, user, schema, values, photos)
    except listing_service.LimitExceeded as e:
        raise HTTPException(429, str(e)) from None

    # уведомление модераторам
    try:
        from app.bot.factory import create_bot
        from app.bot.handlers.moderation import send_to_moderation
        bot = create_bot()
        await send_to_moderation(bot, session, listing)
        await bot.session.close()
    except Exception:
        pass
    return {"public_id": str(listing.public_id), "status": listing.status}
