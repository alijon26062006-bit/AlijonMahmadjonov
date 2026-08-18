"""Панель владельца: товары, склад, заказы, справочники, статистика."""
import hashlib
import hmac
import uuid as uuid_mod
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, Db
from app.catalog.schemas import CATEGORIES, get_category
from app.config import get_settings
from app.db.models import (
    P_ACTIVE, P_HIDDEN, AdminLog, Brand, City, Order, Product, ProductPhoto, User,
)
from app.imaging.style import BACKGROUNDS, STYLE_VERSION
from app.workers import queue
from app.services import order_service, product_service, settings_store
from app.services.product_service import ShopError

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(403, "forbidden")
    return user


Admin = Annotated[User, Depends(require_admin)]


def sign_photo(p: dict) -> str:
    """Подпись загруженного фото: в товар попадает только то, что залито нами."""
    msg = f'{p["file_id"]}|{p["file_unique_id"]}'.encode()
    return hmac.new(get_settings().jwt_secret.encode(), msg,
                    hashlib.sha256).hexdigest()


def _log(session, admin: User, action: str, target: str = "",
         note: str = "") -> None:
    session.add(AdminLog(admin_id=admin.id, action=action,
                         target=target[:120] or None, note=note[:500] or None))


# ─────────────────────────── Товары ───────────────────────────

class ProductIn(BaseModel):
    category: str
    title: str
    description: str = ""
    brand: str | None = None
    old_price: float | None = None
    attrs: dict = {}


class VariantIn(BaseModel):
    size: str = ""
    color: str = ""
    price: float
    stock: int = 0
    sku: str | None = None


class VariantsIn(BaseModel):
    variants: list[VariantIn]


class PhotosIn(BaseModel):
    photos: list[dict]


def _admin_card(product: Product) -> dict:
    return {
        "id": str(product.public_id),
        "category": product.category_slug,
        "title": product.title,
        "brand": product.brand,
        "price": float(product.price),
        "old_price": float(product.old_price) if product.old_price else None,
        "status": product.status,
        "in_stock": product_service.in_stock(product),
        "photos_count": len(product.photos),
        "variants": [{"id": v.id, "size": v.size, "color": v.color,
                      "price": float(v.price), "stock": v.stock, "sku": v.sku}
                     for v in product.variants],
        "photo": (f"/api/photos/{product.photos[0].public_id}?size=thumb"
                  if product.photos else None),
        "sales_count": product.sales_count,
    }


@router.get("/products")
async def products(session: Db, admin: Admin, q: str = "", status: str = "",
                   category: str = "", limit: int = 60):
    query = select(Product).options(selectinload(Product.photos),
                                    selectinload(Product.variants))
    if q.strip():
        needle = f"%{q.strip()[:60]}%"
        query = query.where(or_(Product.title.ilike(needle),
                                Product.brand.ilike(needle)))
    if status:
        query = query.where(Product.status == status)
    if category:
        query = query.where(Product.category_slug == category)
    rows = (await session.scalars(
        query.order_by(Product.updated_at.desc()).limit(min(limit, 200)))).all()
    return {"items": [_admin_card(p) for p in rows],
            "counters": await product_service.counters(session)}


@router.post("/products")
async def create_product(body: ProductIn, session: Db, admin: Admin):
    try:
        product = await product_service.create(
            session, category_slug=body.category, title=body.title,
            description=body.description, brand=body.brand,
            old_price=Decimal(str(body.old_price)) if body.old_price else None,
            attrs=body.attrs)
    except ShopError as e:
        raise HTTPException(400, str(e)) from None
    _log(session, admin, "product_create", product.title)
    await session.commit()
    fresh = await product_service.load(session, product.id)
    return _admin_card(fresh)


@router.patch("/products/{public_id}")
async def update_product(public_id: uuid_mod.UUID, body: ProductIn,
                         session: Db, admin: Admin):
    product = await product_service.load_public(session, public_id)
    if not product:
        raise HTTPException(404, "not_found")
    if get_category(body.category) is None:
        raise HTTPException(400, "unknown_category")
    product.category_slug = body.category
    product.title = " ".join(body.title.split())[:160]
    product.description = body.description.strip()[:4000]
    product.brand = (body.brand or "").strip()[:80] or None
    product.old_price = Decimal(str(body.old_price)) if body.old_price else None
    product.attrs = product_service.clean_attrs(body.category, body.attrs)
    _log(session, admin, "product_update", product.title)
    await session.commit()
    fresh = await product_service.refresh(session,
                                          await product_service.load(session, product.id))
    return _admin_card(fresh)


@router.put("/products/{public_id}/variants")
async def put_variants(public_id: uuid_mod.UUID, body: VariantsIn,
                       session: Db, admin: Admin):
    product = await product_service.load_public(session, public_id)
    if not product:
        raise HTTPException(404, "not_found")
    try:
        fresh = await product_service.set_variants(
            session, product, [v.model_dump() for v in body.variants])
    except ShopError as e:
        raise HTTPException(400, str(e)) from None
    _log(session, admin, "variants", product.title,
         f"{len(body.variants)} вариантов")
    await session.commit()
    return _admin_card(fresh)


@router.put("/products/{public_id}/photos")
async def put_photos(public_id: uuid_mod.UUID, body: PhotosIn,
                     session: Db, admin: Admin):
    product = await product_service.load_public(session, public_id)
    if not product:
        raise HTTPException(404, "not_found")
    for p in body.photos:
        if p.get("sig") != sign_photo(p):
            raise HTTPException(400, "bad_photo_signature")
    fresh = await product_service.set_photos(session, product, body.photos,
                                             get_settings().max_photos)
    return _admin_card(fresh)


@router.post("/products/{public_id}/visibility")
async def visibility(public_id: uuid_mod.UUID, session: Db, admin: Admin,
                     hidden: bool = True):
    product = await product_service.load_public(session, public_id)
    if not product:
        raise HTTPException(404, "not_found")
    product.status = P_HIDDEN if hidden else P_ACTIVE
    await session.commit()
    fresh = await product_service.refresh(
        session, await product_service.load(session, product.id))
    _log(session, admin, "hide" if hidden else "show", product.title)
    await session.commit()
    return _admin_card(fresh)


@router.delete("/products/{public_id}")
async def delete_product(public_id: uuid_mod.UUID, session: Db, admin: Admin):
    product = await product_service.load_public(session, public_id)
    if not product:
        raise HTTPException(404, "not_found")
    _log(session, admin, "product_delete", product.title)
    await session.delete(product)
    await session.commit()
    return {"ok": True}


# ─────────────────────────── Заказы ───────────────────────────

class StatusIn(BaseModel):
    status: str
    tracking: str | None = None
    note: str | None = None


@router.get("/orders")
async def orders(session: Db, admin: Admin, status: str = "", limit: int = 50):
    query = select(Order).options(selectinload(Order.items))
    if status:
        query = query.where(Order.status == status)
    rows = (await session.scalars(
        query.order_by(Order.created_at.desc()).limit(min(limit, 200)))).all()
    return {"items": [await order_service.as_dict(session, o) for o in rows],
            "stats": await order_service.stats(session)}


@router.post("/orders/{order_id}/status")
async def order_status(order_id: int, body: StatusIn, session: Db, admin: Admin):
    try:
        order = await order_service.set_status(
            session, order_id, body.status, tracking=body.tracking,
            note=body.note)
    except ShopError as e:
        raise HTTPException(400, str(e)) from None
    _log(session, admin, "order_status", f"#{order.number}", body.status)
    await session.commit()

    from app.workers.queue import enqueue_order_status
    await enqueue_order_status(order.id)
    return await order_service.as_dict(session, order)


# ─────────────────────────── Справочники и сводка ───────────────

class CityIn(BaseModel):
    name: str
    delivery_days: int = 3


class BrandIn(BaseModel):
    name: str
    areas: list[str] = ["clothes"]


@router.post("/cities")
async def add_city(body: CityIn, session: Db, admin: Admin):
    name = body.name.strip()[:100]
    if not name:
        raise HTTPException(400, "name_required")
    if await session.scalar(select(City).where(City.name == name)):
        raise HTTPException(409, "exists")
    city = City(name=name, delivery_days=max(1, min(body.delivery_days, 30)))
    session.add(city)
    _log(session, admin, "city_add", name)
    await session.commit()
    return {"id": city.id, "name": city.name}


@router.post("/brands")
async def add_brand(body: BrandIn, session: Db, admin: Admin):
    name = body.name.strip()[:80]
    if not name:
        raise HTTPException(400, "name_required")
    existing = await session.scalar(select(Brand).where(Brand.name == name))
    if existing:
        existing.areas = sorted(set(existing.areas) | set(body.areas))
        await session.commit()
        return {"id": existing.id, "name": existing.name}
    brand = Brand(name=name, areas=body.areas or ["clothes"], sort_order=50)
    session.add(brand)
    _log(session, admin, "brand_add", name)
    await session.commit()
    return {"id": brand.id, "name": brand.name}


@router.get("/summary")
async def summary(session: Db, admin: Admin):
    return {
        "products": await product_service.counters(session),
        "orders": await order_service.stats(session),
        "low_stock": [{"title": t, "size": s, "color": c, "stock": n}
                      for t, s, c, n in await product_service.low_stock(session)],
        "categories": [{"slug": c.slug, "title": c.title} for c in CATEGORIES],
    }


@router.get("/log")
async def log(session: Db, admin: Admin, limit: int = 50):
    rows = (await session.execute(
        select(AdminLog, User.first_name)
        .outerjoin(User, User.id == AdminLog.admin_id)
        .order_by(AdminLog.created_at.desc()).limit(min(limit, 200)))).all()
    return {"items": [{"action": a.action, "target": a.target, "note": a.note,
                       "admin": name or "?",
                       "created_at": a.created_at.isoformat() if a.created_at else None}
                      for a, name in rows]}

# ─────────────────────────── Фотографии каталога ───────────────────────────


class StudioIn(BaseModel):
    background: str | None = Field(default=None, max_length=16)


class VersionIn(BaseModel):
    use_processed: bool


class SettingsIn(BaseModel):
    ai_provider: str | None = Field(default=None, max_length=16)
    ai_api_key: str | None = Field(default=None, max_length=200)


def _photo_out(p: ProductPhoto) -> dict:
    return {
        "id": p.id,
        "position": p.position,
        "original": f"/api/photos/{p.public_id}?size=thumb&v=orig",
        "url": f"/api/photos/{p.public_id}?size=thumb",
        "has_processed": bool(p.proc_file_id),
        "use_processed": p.use_processed,
        "background": p.background,
        "style_version": p.style_version,
        "processing": p.processing,
        "error": p.processing_error,
    }


@router.get("/products/{public_id}/photos")
async def product_photos(public_id: uuid_mod.UUID, session: Db, admin: Admin):
    product = await product_service.load_public(session, public_id)
    if product is None:
        raise HTTPException(404, "not_found")
    return {"items": [_photo_out(p) for p in product.photos],
            "backgrounds": [{"key": b.key, "title": b.title}
                            for b in BACKGROUNDS.values()],
            "style_version": STYLE_VERSION}


@router.post("/photos/{photo_id}/studio")
async def studio_one(photo_id: int, body: StudioIn, session: Db, admin: Admin):
    """Подготовить одну фотографию. Оригинал сохраняется в любом случае."""
    photo = await session.get(ProductPhoto, photo_id)
    if photo is None:
        raise HTTPException(404, "not_found")
    photo.processing = "queued"
    photo.processing_error = None
    await session.commit()
    job = await queue.enqueue_photo(photo_id, body.background)
    _log(session, admin, "photo_studio", str(photo_id), body.background or "auto")
    await session.commit()
    return {"job_id": job, "photo": _photo_out(photo)}


@router.post("/products/{public_id}/photos/studio")
async def studio_all(public_id: uuid_mod.UUID, body: StudioIn, session: Db,
                     admin: Admin):
    """Все фотографии товара — одной очередью и с одним фоном."""
    product = await product_service.load_public(session, public_id)
    if product is None:
        raise HTTPException(404, "not_found")
    for photo in product.photos:
        photo.processing = "queued"
        photo.processing_error = None
    await session.commit()
    job = await queue.enqueue_product_photos(product.id, body.background)
    return {"job_id": job, "queued": len(product.photos)}


@router.post("/photos/{photo_id}/version")
async def photo_version(photo_id: int, body: VersionIn, session: Db, admin: Admin):
    """Переключение «оригинал / обработанная». Ничего не удаляет."""
    photo = await session.get(ProductPhoto, photo_id)
    if photo is None:
        raise HTTPException(404, "not_found")
    if body.use_processed and not photo.proc_file_id:
        raise HTTPException(400, "Обработанной версии ещё нет")
    photo.use_processed = body.use_processed
    await session.commit()
    return _photo_out(photo)


@router.get("/settings")
async def read_settings(session: Db, admin: Admin):
    """Ключ наружу не отдаём — только признак, что он задан, и хвост."""
    return await settings_store.public(session)


@router.patch("/settings")
async def write_settings(body: SettingsIn, session: Db, admin: Admin):
    if body.ai_provider is not None:
        if body.ai_provider not in ("local", "removebg"):
            raise HTTPException(400, "Неизвестный способ обработки")
        await settings_store.set_value(session, "ai_provider", body.ai_provider)
    if body.ai_api_key is not None:
        await settings_store.set_value(session, "ai_api_key",
                                       body.ai_api_key.strip())
    _log(session, admin, "settings", "ai", "")
    await session.commit()
    return await settings_store.public(session)
