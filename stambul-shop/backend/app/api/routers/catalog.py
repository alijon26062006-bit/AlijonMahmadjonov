"""Витрина: разделы, список товаров, карточка."""
import uuid as uuid_mod
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import Db, Viewer
from app.catalog.schemas import get_category, groups, serialize
from app.services import categories as categories_service
from app.db.models import P_ACTIVE, P_OUT, Product, ProductEvent, Variant

router = APIRouter(prefix="/api", tags=["catalog"])

PAGE = 24
SORTS = {
    "new": (Product.created_at.desc(), Product.id.desc()),
    "cheap": (Product.price.asc(), Product.id.desc()),
    "expensive": (Product.price.desc(), Product.id.desc()),
    "popular": (Product.sales_count.desc(), Product.views_count.desc(),
                Product.id.desc()),
}


def card(product: Product) -> dict:
    sizes = sorted({v.size for v in product.variants if v.stock > 0 and v.size})
    return {
        "id": str(product.public_id),
        "category": product.category_slug,
        "title": product.title,
        "brand": product.brand,
        "price": float(product.price),
        "old_price": float(product.old_price) if product.old_price else None,
        "status": product.status,
        "in_stock": sum(v.stock for v in product.variants),
        "sizes": sizes,
        "photo": (f"/api/photos/{product.photos[0].public_id}?size=thumb"
                  if product.photos else None),
    }


@router.get("/categories")
async def categories(session: Db):
    await categories_service.sync(session)
    return {"groups": groups()}


@router.get("/categories/{slug}")
async def category_schema(slug: str, session: Db):
    await categories_service.sync(session)
    category = get_category(slug)
    if category is None:
        raise HTTPException(404, "not_found")
    return serialize(category)


@router.get("/products")
async def list_products(request: Request, session: Db,
                        viewer: Viewer):
    await categories_service.sync(session)
    params = dict(request.query_params)
    query = select(Product).where(Product.status.in_((P_ACTIVE, P_OUT)))

    category = get_category(params.get("category", ""))
    if params.get("category") and category is None:
        raise HTTPException(404, "unknown_category")
    if category:
        query = query.where(Product.category_slug == category.slug)

    if (q := (params.get("q") or "").strip()):
        needle = f"%{q[:60]}%"
        query = query.where(or_(Product.title.ilike(needle),
                                Product.brand.ilike(needle),
                                Product.description.ilike(needle)))
    if params.get("brand"):
        query = query.where(Product.brand == params["brand"][:80])
    if params.get("price_min"):
        query = query.where(Product.price >= Decimal(params["price_min"]))
    if params.get("price_max"):
        query = query.where(Product.price <= Decimal(params["price_max"]))
    if params.get("in_stock") == "1":
        query = query.where(Product.status == P_ACTIVE)
    if params.get("size"):
        # размер живёт в вариантах — ищем среди тех, что ещё есть
        query = query.where(Product.id.in_(
            select(Variant.product_id).where(Variant.size == params["size"][:24],
                                             Variant.stock > 0)))

    # Фильтры по полям раздела: только те ключи, что описаны в схеме
    if category:
        for field in category.fields:
            value = params.get(field.key)
            if not value or field.filter == "none":
                continue
            if field.filter == "multiselect":
                wanted = [v for v in value.split(",") if v]
                if field.options:
                    wanted = [v for v in wanted if v in field.options]
                if wanted:
                    query = query.where(
                        cast(Product.attrs[field.key], String).in_(
                            [f'"{v}"' for v in wanted]))
            elif field.filter == "range":
                try:
                    query = query.where(
                        Product.attrs[field.key].astext.cast(func.numeric)
                        >= Decimal(value))
                except Exception:
                    pass

    order = SORTS.get(params.get("sort", "new"), SORTS["new"])
    page = max(0, int(params.get("page", 0) or 0))
    rows = (await session.scalars(
        query.options(selectinload(Product.photos), selectinload(Product.variants))
        .order_by(*order).offset(page * PAGE).limit(PAGE + 1))).all()

    has_more = len(rows) > PAGE
    return {"items": [card(p) for p in rows[:PAGE]], "has_more": has_more,
            "page": page}


@router.get("/products/{public_id}")
async def product_detail(public_id: uuid_mod.UUID, session: Db,
                         viewer: Viewer):
    product = (await session.scalars(
        select(Product).where(Product.public_id == public_id)
        .options(selectinload(Product.photos),
                 selectinload(Product.variants)))).first()
    if not product:
        raise HTTPException(404, "not_found")
    is_admin = bool(viewer and viewer.is_admin)
    if product.status not in (P_ACTIVE, P_OUT) and not is_admin:
        raise HTTPException(404, "not_found")

    product.views_count += 1
    session.add(ProductEvent(product_id=product.id,
                             user_id=viewer.id if viewer else None, kind="view"))
    await session.commit()

    category = get_category(product.category_slug)
    specs = []
    if category:
        for field in category.fields:
            value = product.attrs.get(field.key)
            if value in (None, "", []):
                continue
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            specs.append({"label": field.label, "value": str(value),
                          "unit": field.unit})

    out = card(product)
    out.update({
        "description": product.description,
        "category_title": category.title if category else product.category_slug,
        "photos": [{"full": f"/api/photos/{p.public_id}",
                    "thumb": f"/api/photos/{p.public_id}?size=thumb"}
                   for p in product.photos],
        "specs": specs,
        "views_count": product.views_count,
        "variants": [{"id": v.id, "size": v.size, "color": v.color,
                      "label": v.label, "price": float(v.price),
                      "stock": v.stock}
                     for v in product.variants],
    })
    return out


@router.get("/products/{public_id}/similar")
async def similar(public_id: uuid_mod.UUID, session: Db, limit: int = 8):
    """Похожие: тот же раздел, ближайшая цена. Помогает, когда размер кончился."""
    product = await session.scalar(
        select(Product).where(Product.public_id == public_id))
    if not product:
        raise HTTPException(404, "not_found")
    rows = (await session.scalars(
        select(Product)
        .where(Product.status == P_ACTIVE,
               Product.category_slug == product.category_slug,
               Product.id != product.id)
        .options(selectinload(Product.photos), selectinload(Product.variants))
        .order_by(func.abs(Product.price - product.price))
        .limit(min(limit, 20)))).all()
    return {"items": [card(p) for p in rows]}
