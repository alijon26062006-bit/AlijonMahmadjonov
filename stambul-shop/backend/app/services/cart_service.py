"""Корзина.

Живёт в базе, а не в браузере: человек кладёт вещь с телефона, открывает
с компьютера — корзина на месте. Остаток при этом не резервируется: пока
заказ не оформлен, вещь может купить кто-то другой, и мы честно скажем об
этом при оформлении, а не тихо продадим одно и то же дважды.
"""
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import CartItem, P_ACTIVE, Product, User, Variant
from app.services.product_service import ShopError

MAX_QTY = 20


async def _rows(session: AsyncSession, user: User) -> list[tuple[CartItem, Variant, Product]]:
    return list((await session.execute(
        select(CartItem, Variant, Product)
        .join(Variant, Variant.id == CartItem.variant_id)
        .join(Product, Product.id == Variant.product_id)
        .where(CartItem.user_id == user.id)
        .options(selectinload(Product.photos))
        .order_by(CartItem.added_at))).all())


async def add(session: AsyncSession, user: User, variant_id: int,
              qty: int = 1, limit: int = 30) -> CartItem:
    qty = max(1, min(int(qty), MAX_QTY))
    variant = await session.get(Variant, variant_id)
    if variant is None:
        raise ShopError("Такого товара нет")
    product = await session.get(Product, variant.product_id)
    if product is None or product.status != P_ACTIVE:
        raise ShopError("Товар сейчас не продаётся")
    if variant.stock < 1:
        raise ShopError("Этот размер закончился")

    item = await session.scalar(
        select(CartItem).where(CartItem.user_id == user.id,
                               CartItem.variant_id == variant_id))
    if item is None:
        count = len(await _rows(session, user))
        if count >= limit:
            raise ShopError("В корзине слишком много товаров")
        item = CartItem(user_id=user.id, variant_id=variant_id, qty=0)
        session.add(item)
    item.qty = min(item.qty + qty, MAX_QTY, variant.stock)
    await session.commit()
    await session.refresh(item)
    return item


async def set_qty(session: AsyncSession, user: User, variant_id: int,
                  qty: int) -> None:
    item = await session.scalar(
        select(CartItem).where(CartItem.user_id == user.id,
                               CartItem.variant_id == variant_id))
    if item is None:
        return
    if qty <= 0:
        await session.delete(item)
    else:
        variant = await session.get(Variant, variant_id)
        item.qty = min(int(qty), MAX_QTY, variant.stock if variant else MAX_QTY)
    await session.commit()


async def remove(session: AsyncSession, user: User, variant_id: int) -> None:
    await session.execute(
        delete(CartItem).where(CartItem.user_id == user.id,
                               CartItem.variant_id == variant_id))
    await session.commit()


async def clear(session: AsyncSession, user: User) -> None:
    await session.execute(delete(CartItem).where(CartItem.user_id == user.id))
    await session.commit()


async def contents(session: AsyncSession, user: User) -> dict:
    """Корзина для показа: строки, сумма и предупреждения об остатках."""
    items, total, issues = [], Decimal("0"), []
    for item, variant, product in await _rows(session, user):
        available = variant.stock if product.status == P_ACTIVE else 0
        qty = min(item.qty, available)
        if available == 0:
            issues.append(f"«{product.title}» ({variant.label}) закончился")
        elif qty < item.qty:
            issues.append(f"«{product.title}» ({variant.label}): осталось {available}")
        line = Decimal(str(variant.price)) * qty
        total += line
        photo = product.photos[0] if product.photos else None
        items.append({
            "variant_id": variant.id,
            "product_id": str(product.public_id),
            "title": product.title,
            "variant": variant.label,
            "price": float(variant.price),
            "qty": item.qty,
            "available": available,
            "line_total": float(line),
            "photo": f"/api/photos/{photo.public_id}?size=thumb" if photo else None,
        })
    return {"items": items, "goods_total": float(total),
            "count": sum(i["qty"] for i in items), "issues": issues}
