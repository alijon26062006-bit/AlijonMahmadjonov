"""Товары и их варианты.

Правило, вокруг которого всё построено: остаток живёт только в варианте.
Состояние карточки — производная от вариантов, а не отдельная воля человека:
кончились все размеры — товар уходит из каталога сам и возвращается, когда
завезли. Поэтому пересчёт вызывается после любого изменения вариантов.
"""
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.catalog.schemas import get_category
from app.db.models import (
    P_ACTIVE, P_DRAFT, P_HIDDEN, P_OUT, Product, ProductPhoto, Variant,
)


class ShopError(Exception):
    """Ошибка, которую нужно показать человеку словами."""


# populate_existing обязателен: объект уже может лежать в сессии с ранее
# загруженными вариантами, и без этого флага SQLAlchemy вернёт старый список,
# а пересчёт цены и состояния увидит товар пустым.
def _full(query):
    return (query.options(selectinload(Product.variants),
                          selectinload(Product.photos))
            .execution_options(populate_existing=True))


async def load(session: AsyncSession, product_id: int) -> Product | None:
    return (await session.scalars(
        _full(select(Product).where(Product.id == product_id)))).first()


async def load_public(session: AsyncSession, public_id) -> Product | None:
    return (await session.scalars(
        _full(select(Product).where(Product.public_id == public_id)))).first()


def in_stock(product: Product) -> int:
    return sum(v.stock for v in product.variants)


async def refresh(session: AsyncSession, product: Product) -> Product:
    """Пересчитывает цену «от» и состояние по вариантам.

    Скрытый вручную товар остаётся скрытым: это решение человека, а не склада.
    Черновик оживает сам, как только у него появляются товар и фотография —
    иначе легко забыть нажать «опубликовать».
    """
    live = [v for v in product.variants if v.stock > 0]
    prices = [Decimal(str(v.price)) for v in (live or product.variants)]
    product.price = min(prices) if prices else Decimal("0")

    if product.status == P_HIDDEN:
        pass                                   # снят вручную — не трогаем
    elif not product.variants or not product.photos:
        product.status = P_DRAFT               # нечего показывать
    elif not live:
        product.status = P_OUT
    else:
        product.status = P_ACTIVE
    await session.commit()
    await session.refresh(product)
    return product


async def create(session: AsyncSession, *, category_slug: str, title: str,
                 description: str = "", brand: str | None = None,
                 old_price: Decimal | None = None,
                 attrs: dict | None = None) -> Product:
    category = get_category(category_slug)
    if category is None:
        raise ShopError("Такого раздела нет")
    title = " ".join(title.split())[:160]
    if len(title) < 3:
        raise ShopError("Название слишком короткое")

    product = Product(
        category_slug=category_slug, title=title,
        description=description.strip()[:4000],
        brand=(brand or "").strip()[:80] or None,
        old_price=old_price,
        attrs=clean_attrs(category_slug, attrs or {}),
        status=P_DRAFT)
    session.add(product)
    await session.commit()
    # возвращаем с загруженными связями: иначе следующий вызов полезет за
    # вариантами лениво, а в асинхронной сессии это падает
    return await load(session, product.id)


def clean_attrs(category_slug: str, raw: dict) -> dict:
    """Оставляет только поля своего раздела и только допустимые значения.

    С формы может прийти что угодно; в базу должно попасть то, что описано
    в схеме, иначе фильтры каталога начнут показывать мусор.
    """
    category = get_category(category_slug)
    if category is None:
        return {}
    out: dict = {}
    for field in category.fields:
        if field.key not in raw:
            continue
        value = raw[field.key]
        if value in (None, "", []):
            continue
        if field.type == "int":
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
            if (field.min is not None and value < field.min) or \
                    (field.max is not None and value > field.max):
                continue
        elif field.type == "bool":
            value = bool(value)
        elif field.options:
            allowed = set(field.options)
            if field.type == "enum_many":
                value = [v for v in (value if isinstance(value, list) else [value])
                         if str(v) in allowed]
                if not value:
                    continue
            elif str(value) not in allowed:
                continue
        else:
            value = str(value).strip()[:200]
            if not value:
                continue
        out[field.key] = value
    return out


async def set_variants(session: AsyncSession, product: Product,
                       rows: list[dict]) -> Product:
    """Заменяет набор вариантов целиком.

    Так проще и честнее, чем править по одному: продавец видит таблицу
    «размер — цвет — цена — остаток» и сохраняет её как есть. Варианты,
    которые уже лежат в чьих-то заказах, остаются в истории заказа снимком.
    """
    product = await load(session, product.id) or product
    seen: set[tuple[str, str]] = set()
    prepared: list[dict] = []
    for i, row in enumerate(rows):
        size = str(row.get("size", "")).strip()[:24]
        color = str(row.get("color", "")).strip()[:40]
        key = (size.lower(), color.lower())
        if key in seen:
            raise ShopError(f"Вариант «{size} {color}» повторяется")
        seen.add(key)
        try:
            price = Decimal(str(row["price"]))
        except Exception:
            raise ShopError("Цена варианта указана неверно") from None
        if price <= 0:
            raise ShopError("Цена должна быть больше нуля")
        stock = int(row.get("stock") or 0)
        if stock < 0:
            raise ShopError("Остаток не может быть отрицательным")
        prepared.append({"size": size, "color": color, "price": price,
                         "stock": stock, "sku": (row.get("sku") or None),
                         "sort_order": i})
    if not prepared:
        raise ShopError("Нужен хотя бы один вариант")

    # старые варианты заменяем, сохраняя те же строки при совпадении
    existing = {(v.size.lower(), v.color.lower()): v for v in product.variants}
    keep: set[int] = set()
    for row in prepared:
        key = (row["size"].lower(), row["color"].lower())
        variant = existing.get(key)
        if variant is None:
            variant = Variant(product_id=product.id)
            session.add(variant)
        variant.size, variant.color = row["size"], row["color"]
        variant.price, variant.stock = row["price"], row["stock"]
        variant.sku, variant.sort_order = row["sku"], row["sort_order"]
        if variant.id:
            keep.add(variant.id)
    for variant in product.variants:
        if variant.id and variant.id not in keep:
            await session.delete(variant)
    await session.commit()

    fresh = await load(session, product.id)
    return await refresh(session, fresh)


async def set_photos(session: AsyncSession, product: Product,
                     photos: list[dict], max_photos: int) -> Product:
    product = await load(session, product.id) or product
    for photo in product.photos:
        await session.delete(photo)
    await session.flush()
    for i, p in enumerate(photos[:max_photos]):
        session.add(ProductPhoto(
            product_id=product.id, file_id=p["file_id"],
            thumb_file_id=p.get("thumb_file_id"),
            thumb_w=p["thumb_w"] if isinstance(p.get("thumb_w"), int) else None,
            file_unique_id=p["file_unique_id"],
            width=p.get("width"), height=p.get("height"), position=i))
    await session.commit()

    fresh = await load(session, product.id)
    return await refresh(session, fresh)


async def take_stock(session: AsyncSession, variant_id: int, qty: int) -> Variant:
    """Списывает остаток под заказ. Блокирует строку: два покупателя не должны
    купить одну и ту же последнюю вещь."""
    variant = await session.scalar(
        select(Variant).where(Variant.id == variant_id).with_for_update())
    if variant is None:
        raise ShopError("Товар больше не продаётся")
    if variant.stock < qty:
        raise ShopError(f"Осталось только {variant.stock} шт.")
    variant.stock -= qty
    return variant


async def return_stock(session: AsyncSession, variant_id: int, qty: int) -> None:
    """Возвращает остаток при отмене заказа."""
    variant = await session.scalar(
        select(Variant).where(Variant.id == variant_id).with_for_update())
    if variant is not None:
        variant.stock += qty


async def low_stock(session: AsyncSession, threshold: int = 2) -> list[tuple]:
    """Что заканчивается — для панели."""
    rows = (await session.execute(
        select(Product.title, Variant.size, Variant.color, Variant.stock)
        .join(Variant, Variant.product_id == Product.id)
        .where(Variant.stock <= threshold, Variant.stock > 0,
               Product.status == P_ACTIVE)
        .order_by(Variant.stock).limit(20))).all()
    return list(rows)


async def counters(session: AsyncSession) -> dict:
    async def count(*conds) -> int:
        return await session.scalar(
            select(func.count()).select_from(Product).where(*conds)) or 0

    total_stock = await session.scalar(select(func.sum(Variant.stock))) or 0
    return {
        "active": await count(Product.status == P_ACTIVE),
        "draft": await count(Product.status == P_DRAFT),
        "hidden": await count(Product.status == P_HIDDEN),
        "out": await count(Product.status == P_OUT),
        "units": int(total_stock),
    }
