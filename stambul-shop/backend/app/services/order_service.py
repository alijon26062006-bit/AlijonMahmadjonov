"""Заказы: оформление, статусы, возврат остатков.

Оформление — единственное место, где списывается склад. Делается одной
транзакцией с блокировкой строк: если два человека одновременно берут
последнюю вещь, второй получит внятный отказ, а не молчаливый минус.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db.models import (
    O_CANCELED, O_DONE, O_NEW, O_PAID, ORDER_FLOW, CartItem, City, Order,
    OrderItem, Product, ProductEvent, User, Variant,
)
from app.services import product_service
from app.services.product_service import ShopError

DELIVERY_LABELS = {
    "pickup": "Самовывоз",
    "courier": "Курьером по городу",
    "post": "Почтой по Казахстану",
}

STATUS_LABELS = {
    "new": "Новый",
    "confirmed": "Подтверждён",
    "paid": "Оплачен",
    "shipped": "Отправлен",
    "done": "Получен",
    "canceled": "Отменён",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def delivery_price(delivery: str, goods_total: Decimal) -> Decimal:
    s = get_settings()
    if delivery == "pickup":
        return Decimal("0")
    if s.free_delivery_from and goods_total >= s.free_delivery_from:
        return Decimal("0")
    price = s.delivery_city_price if delivery == "courier" else s.delivery_country_price
    return Decimal(str(price))


async def create(session: AsyncSession, user: User, *, customer_name: str,
                 phone: str, city_id: int | None, address: str | None,
                 delivery: str, comment: str | None = None) -> Order:
    s = get_settings()
    if delivery not in DELIVERY_LABELS:
        raise ShopError("Выберите способ доставки")
    if delivery == "pickup" and not s.pickup_address:
        raise ShopError("Самовывоз сейчас недоступен")
    customer_name = " ".join((customer_name or "").split())[:128]
    if len(customer_name) < 2:
        raise ShopError("Укажите имя")
    phone = (phone or "").strip()[:20]
    if len(phone) < 10:
        raise ShopError("Укажите номер телефона")
    if delivery != "pickup" and not city_id:
        raise ShopError("Выберите город")
    if delivery != "pickup" and not (address or "").strip():
        raise ShopError("Укажите адрес доставки")

    rows = list((await session.execute(
        select(CartItem, Variant, Product)
        .join(Variant, Variant.id == CartItem.variant_id)
        .join(Product, Product.id == Variant.product_id)
        .where(CartItem.user_id == user.id))).all())
    if not rows:
        raise ShopError("Корзина пуста")

    order = Order(number=0, user_id=user.id, status=O_NEW,
                  customer_name=customer_name, phone=phone,
                  city_id=city_id, address=(address or "").strip()[:255] or None,
                  delivery=delivery, comment=(comment or "").strip()[:500] or None)
    session.add(order)
    await session.flush()
    order.number = 1000 + order.id          # короткий номер для переписки

    goods_total = Decimal("0")
    for item, variant, product in rows:
        # списываем склад под блокировкой — здесь решается, кому досталось
        taken = await product_service.take_stock(session, variant.id, item.qty)
        price = Decimal(str(taken.price))
        goods_total += price * item.qty
        session.add(OrderItem(
            order_id=order.id, variant_id=variant.id, product_id=product.id,
            title=product.title, variant_label=variant.label,
            price=price, qty=item.qty))
        session.add(ProductEvent(product_id=product.id, user_id=user.id,
                                 kind="purchase"))
        product.sales_count += item.qty

    if s.order_min_total and goods_total < s.order_min_total:
        raise ShopError(f"Минимальная сумма заказа — {s.order_min_total} {s.currency_sign}")

    order.goods_total = goods_total
    order.delivery_price = delivery_price(delivery, goods_total)
    order.total = goods_total + order.delivery_price

    # адрес запоминаем: в следующий раз подставится сам
    user.phone, user.city_id, user.address = phone, city_id, order.address
    await session.execute(CartItem.__table__.delete().where(
        CartItem.user_id == user.id))
    await session.commit()

    # пересчитываем состояния товаров: что-то могло закончиться этим заказом
    for _, variant, _ in rows:
        product = await product_service.load(session, variant.product_id)
        if product:
            await product_service.refresh(session, product)

    return await load(session, order.id)


async def load(session: AsyncSession, order_id: int) -> Order | None:
    return (await session.scalars(
        select(Order).where(Order.id == order_id)
        .options(selectinload(Order.items)))).first()


async def set_status(session: AsyncSession, order_id: int, status: str,
                     *, tracking: str | None = None,
                     note: str | None = None) -> Order:
    order = await session.scalar(
        select(Order).where(Order.id == order_id).with_for_update())
    if order is None:
        raise ShopError("Заказ не найден")
    if status == order.status:
        return await load(session, order_id)
    allowed = ORDER_FLOW.get(order.status, ())
    if status not in allowed:
        raise ShopError(
            f"Из «{STATUS_LABELS.get(order.status, order.status)}» нельзя перейти "
            f"в «{STATUS_LABELS.get(status, status)}»")

    if status == O_CANCELED:
        # возвращаем вещи на склад — иначе они пропадут из продажи навсегда
        items = list(await session.scalars(
            select(OrderItem).where(OrderItem.order_id == order.id)))
        for item in items:
            if item.variant_id:
                await product_service.return_stock(session, item.variant_id, item.qty)
            if item.product_id:
                product = await session.get(Product, item.product_id)
                if product:
                    product.sales_count = max(0, product.sales_count - item.qty)
    if status == O_PAID:
        order.paid_at = _now()
    if status == O_DONE:
        order.done_at = _now()
    if tracking is not None:
        order.tracking = tracking.strip()[:64] or None
    if note is not None:
        order.admin_note = note.strip()[:500] or None
    order.status = status
    await session.commit()

    if status == O_CANCELED:
        for item in await session.scalars(
                select(OrderItem).where(OrderItem.order_id == order.id)):
            if item.product_id:
                product = await product_service.load(session, item.product_id)
                if product:
                    await product_service.refresh(session, product)
    return await load(session, order_id)


async def as_dict(session: AsyncSession, order: Order) -> dict:
    city = await session.get(City, order.city_id) if order.city_id else None
    return {
        "id": order.id,
        "public_id": str(order.public_id),
        "number": order.number,
        "status": order.status,
        "status_label": STATUS_LABELS.get(order.status, order.status),
        "next_statuses": list(ORDER_FLOW.get(order.status, ())),
        "customer_name": order.customer_name,
        "phone": order.phone,
        "city": city.name if city else None,
        "address": order.address,
        "delivery": order.delivery,
        "delivery_label": DELIVERY_LABELS.get(order.delivery, order.delivery),
        "comment": order.comment,
        "goods_total": float(order.goods_total),
        "delivery_price": float(order.delivery_price),
        "total": float(order.total),
        "tracking": order.tracking,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "items": [{"title": i.title, "variant": i.variant_label,
                   "price": float(i.price), "qty": i.qty,
                   "line_total": float(Decimal(str(i.price)) * i.qty)}
                  for i in order.items],
    }


async def stats(session: AsyncSession, days: int = 7) -> dict:
    since = _now() - timedelta(days=days)
    today = _now() - timedelta(days=1)

    async def count(*conds) -> int:
        return await session.scalar(
            select(func.count()).select_from(Order).where(*conds)) or 0

    async def money(*conds) -> float:
        return float(await session.scalar(
            select(func.coalesce(func.sum(Order.total), 0)).where(*conds)) or 0)

    paid_states = (O_PAID, "shipped", O_DONE)
    return {
        "new": await count(Order.status == O_NEW),
        "in_work": await count(Order.status.in_(("confirmed", O_PAID, "shipped"))),
        "done": await count(Order.status == O_DONE),
        "canceled": await count(Order.status == O_CANCELED),
        "today": await count(Order.created_at > today),
        "week": await count(Order.created_at > since),
        "revenue_week": await money(Order.status.in_(paid_states),
                                    Order.created_at > since),
        "revenue_total": await money(Order.status.in_(paid_states)),
        "average": round(await money(Order.status.in_(paid_states))
                         / max(1, await count(Order.status.in_(paid_states)))),
    }
