"""Магазин целиком: товар с размерами → корзина → заказ → статусы → склад."""
import asyncio
import sys
from decimal import Decimal

from common import check, login, report

ADMIN_TG = 7418217143
BUYER_TG = 810001
OTHER_TG = 810002
ADMIN_PHONE = "+77010000101"
BUYER_PHONE = "+77010000102"
OTHER_PHONE = "+77010000103"


async def main():
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select

    from app.api.main import app
    from app.api.routers.admin import sign_photo
    from app.catalog.schemas import CATEGORIES, get_category
    from app.db.base import SessionMaker
    from app.db.models import (
        O_CANCELED, O_CONFIRMED, O_DONE, O_NEW, O_PAID, P_ACTIVE, P_DRAFT,
        P_OUT, CartItem, City, Order, Product, User, Variant,
    )
    from app.services import cart_service, order_service, product_service

    async with SessionMaker() as session:
        for table in (CartItem, Order, Product):
            await session.execute(table.__table__.delete())
        await session.execute(User.__table__.delete())
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        # ── 1. Вход ─────────────────────────────────────────────────────
        admin_tok = await login(c, ADMIN_PHONE, ADMIN_TG, "Алиджон")
        AH = {"Authorization": f"Bearer {admin_tok}"}
        r = await c.get("/api/auth/me", headers=AH)
        check(r.json()["is_admin"] is True,
              "Владелец магазина определяется по ADMIN_IDS")

        buyer_tok = await login(c, BUYER_PHONE, BUYER_TG, "Айгуль")
        BH = {"Authorization": f"Bearer {buyer_tok}"}
        r = await c.get("/api/auth/me", headers=BH)
        check(r.json()["is_admin"] is False, "Покупатель — не админ")

        # ── 2. Разделы магазина ─────────────────────────────────────────
        r = await c.get("/api/categories")
        names = [g["title"] for g in r.json()["groups"]]
        check(len(CATEGORIES) == 10 and "Одежда" in names,
              "Десять разделов в четырёх группах", names)

        r = await c.get("/api/categories/shoes")
        js = r.json()
        check(js["size_scales"][0]["sizes"][0] == "35",
              "У обуви своя размерная линейка", js["size_scales"][0]["sizes"][:3])
        check(len(js["colors"]) > 10, "Цвета предлагаются списком")

        # ── 3. Заведение товара ─────────────────────────────────────────
        r = await c.post("/api/admin/products", headers=BH, json={
            "category": "women_clothes", "title": "Платье летнее"})
        check(r.status_code == 403, "Покупатель товар не заведёт", r.status_code)

        r = await c.post("/api/admin/products", headers=AH, json={
            "category": "women_clothes",
            "title": "Платье летнее в цветочек",
            "description": "Лёгкое платье из хлопка, Турция",
            "brand": "Koton",
            "attrs": {"kind": "Платье", "season": "Лето",
                      "made_in": "Турция", "чужое": "поле"}})
        check(r.status_code == 200, "Товар заведён", r.status_code)
        dress = r.json()
        check(dress["status"] == P_DRAFT,
              "Пока нет фото и размеров — это черновик", dress["status"])

        async with SessionMaker() as session:
            product = await session.scalar(select(Product))
            check("чужое" not in product.attrs and product.attrs["kind"] == "Платье",
                  "Чужие поля отброшены, свои сохранены", product.attrs)

        # ── 4. Размеры и остатки ────────────────────────────────────────
        pid = dress["id"]
        r = await c.put(f"/api/admin/products/{pid}/variants", headers=AH, json={
            "variants": [
                {"size": "S", "color": "Чёрный", "price": 12000, "stock": 2},
                {"size": "M", "color": "Чёрный", "price": 12000, "stock": 3},
                {"size": "L", "color": "Чёрный", "price": 12500, "stock": 0},
            ]})
        check(r.status_code == 200, "Варианты сохранены", r.status_code)
        check(r.json()["price"] == 12000,
              "Цена карточки — минимальная из доступных", r.json()["price"])
        check(r.json()["status"] == P_DRAFT,
              "Без фотографии товар всё ещё черновик", r.json()["status"])

        r = await c.put(f"/api/admin/products/{pid}/variants", headers=AH, json={
            "variants": [{"size": "S", "color": "Чёрный", "price": 0, "stock": 1}]})
        check(r.status_code == 400, "Нулевая цена отклонена", r.json().get("detail"))

        r = await c.put(f"/api/admin/products/{pid}/variants", headers=AH, json={
            "variants": [{"size": "S", "color": "Чёрный", "price": 100, "stock": 1},
                         {"size": "s", "color": "чёрный", "price": 100, "stock": 1}]})
        check(r.status_code == 400, "Повтор размера и цвета отклонён",
              r.json().get("detail"))

        # ── 5. Фотография оживляет карточку ─────────────────────────────
        photo = {"file_id": "AgAC-dress", "file_unique_id": "uq-dress-1",
                 "thumb_file_id": "AgAC-dress-t", "thumb_w": 800,
                 "width": 1280, "height": 1600}
        photo["sig"] = sign_photo(photo)
        r = await c.put(f"/api/admin/products/{pid}/photos", headers=AH,
                        json={"photos": [photo]})
        check(r.json()["status"] == P_ACTIVE,
              "С фото и остатком товар в продаже", r.json()["status"])

        bad = dict(photo, sig="подделка")
        r = await c.put(f"/api/admin/products/{pid}/photos", headers=AH,
                        json={"photos": [bad]})
        check(r.status_code == 400, "Чужое фото не принимается", r.status_code)

        # вернём нормальные варианты
        await c.put(f"/api/admin/products/{pid}/variants", headers=AH, json={
            "variants": [
                {"size": "S", "color": "Чёрный", "price": 12000, "stock": 2},
                {"size": "M", "color": "Чёрный", "price": 12000, "stock": 3},
                {"size": "L", "color": "Чёрный", "price": 12500, "stock": 0},
            ]})

        # ── 6. Витрина ──────────────────────────────────────────────────
        r = await c.get("/api/products")
        items = r.json()["items"]
        check(len(items) == 1 and items[0]["sizes"] == ["M", "S"],
              "В каталоге показаны только размеры в наличии", items[0]["sizes"])
        check(items[0]["photo"], "Фотография отдаётся")

        r = await c.get("/api/products?category=shoes")
        check(r.json()["items"] == [], "Чужой раздел пуст")

        r = await c.get("/api/products?q=платье")
        check(len(r.json()["items"]) == 1, "Поиск по названию находит")

        r = await c.get("/api/products?season=Лето")
        check(len(r.json()["items"]) == 1, "Фильтр по полю раздела работает")
        r = await c.get("/api/products?category=women_clothes&season=Зима")
        check(r.json()["items"] == [], "Не тот сезон — ничего не находит")

        r = await c.get(f"/api/products/{pid}")
        detail = r.json()
        check(len(detail["variants"]) == 3, "В карточке все варианты",
              len(detail["variants"]))
        check(any(s["label"] == "Сезон" for s in detail["specs"]),
              "Характеристики собраны из схемы")

        # ── 7. Корзина ──────────────────────────────────────────────────
        vs = {v["size"]: v["id"] for v in detail["variants"]}
        r = await c.post("/api/cart", headers=BH,
                         json={"variant_id": vs["L"], "qty": 1})
        check(r.status_code == 400, "Закончившийся размер в корзину не кладётся",
              r.json().get("detail"))

        r = await c.post("/api/cart", headers=BH,
                         json={"variant_id": vs["M"], "qty": 2})
        cart = r.json()
        check(cart["count"] == 2 and cart["goods_total"] == 24000,
              "Товар в корзине, сумма посчитана", cart["goods_total"])

        r = await c.post("/api/cart", headers=BH,
                         json={"variant_id": vs["M"], "qty": 5})
        check(r.json()["items"][0]["qty"] == 3,
              "Больше остатка положить нельзя", r.json()["items"][0]["qty"])

        r = await c.patch(f"/api/cart/{vs['M']}", headers=BH, json={"qty": 1})
        check(r.json()["count"] == 1, "Количество меняется", r.json()["count"])

        # ── 8. Оформление заказа ────────────────────────────────────────
        async with SessionMaker() as session:
            city = await session.scalar(select(City).where(City.name == "Алматы"))
            city_id = city.id

        r = await c.post("/api/orders", headers=BH, json={
            "customer_name": "А", "phone": "87011234567",
            "city_id": city_id, "address": "Абая 1", "delivery": "courier"})
        check(r.status_code == 400, "Слишком короткое имя не принимается",
              r.json().get("detail"))

        r = await c.post("/api/orders", headers=BH, json={
            "customer_name": "Айгуль", "phone": "87011234567",
            "city_id": city_id, "delivery": "courier"})
        check(r.status_code == 400, "Без адреса курьером нельзя",
              r.json().get("detail"))

        r = await c.post("/api/orders", headers=BH, json={
            "customer_name": "Айгуль", "phone": "87011234567",
            "city_id": city_id, "address": "Абая 1, кв 5",
            "delivery": "courier", "comment": "Позвонить за час"})
        check(r.status_code == 200, "Заказ оформлен", r.status_code)
        order = r.json()
        check(order["number"] >= 1000, "Номер заказа человеческий", order["number"])
        check(order["goods_total"] == 12000 and order["delivery_price"] == 1500
              and order["total"] == 13500,
              "Доставка добавлена к сумме", order["total"])
        check(order["status"] == O_NEW, "Статус — новый", order["status"])

        r = await c.get("/api/cart", headers=BH)
        check(r.json()["count"] == 0, "Корзина очищена после заказа")

        async with SessionMaker() as session:
            variant = await session.get(Variant, vs["M"])
            check(variant.stock == 2, "Со склада списана одна вещь", variant.stock)
            buyer = await session.scalar(select(User).where(User.tg_id == BUYER_TG))
            check(buyer.phone == "87011234567" and buyer.address == "Абая 1, кв 5",
                  "Адрес запомнен для следующего заказа")

        # ── 9. Бесплатная доставка от суммы ─────────────────────────────
        await c.post("/api/cart", headers=BH, json={"variant_id": vs["S"], "qty": 2})
        r = await c.post("/api/orders", headers=BH, json={
            "customer_name": "Айгуль", "phone": "87011234567",
            "city_id": city_id, "address": "Абая 1, кв 5", "delivery": "courier"})
        big = r.json()
        check(big["goods_total"] == 24000 and big["delivery_price"] == 1500,
              "До порога доставка платная", big["delivery_price"])

        # ── 10. Последнюю вещь не продаём дважды ────────────────────────
        other_tok = await login(c, OTHER_PHONE, OTHER_TG, "Данияр")
        OH = {"Authorization": f"Bearer {other_tok}"}
        async with SessionMaker() as session:
            variant = await session.get(Variant, vs["M"])
            variant.stock = 1
            await session.commit()

        await c.post("/api/cart", headers=BH, json={"variant_id": vs["M"], "qty": 1})
        await c.post("/api/cart", headers=OH, json={"variant_id": vs["M"], "qty": 1})
        first = await c.post("/api/orders", headers=BH, json={
            "customer_name": "Айгуль", "phone": "87011234567",
            "city_id": city_id, "address": "Абая 1", "delivery": "courier"})
        second = await c.post("/api/orders", headers=OH, json={
            "customer_name": "Данияр", "phone": "87019998877",
            "city_id": city_id, "address": "Сейфуллина 2", "delivery": "courier"})
        check(first.status_code == 200 and second.status_code == 400,
              "Последнюю вещь получил только первый",
              second.json().get("detail"))

        # ── 11. Товар закончился — уходит с витрины сам ─────────────────
        async with SessionMaker() as session:
            product = await session.scalar(select(Product))
            for v in (await session.scalars(
                    select(Variant).where(Variant.product_id == product.id))):
                v.stock = 0
            await session.commit()
            fresh = await product_service.load(session, product.id)
            fresh = await product_service.refresh(session, fresh)
            check(fresh.status == P_OUT, "Нет остатка — статус «закончился»",
                  fresh.status)

        r = await c.get("/api/products?in_stock=1")
        check(r.json()["items"] == [], "В наличии — ничего не показывает")
        r = await c.get("/api/products")
        check(len(r.json()["items"]) == 1,
              "Но карточка остаётся видимой, чтобы люди спросили о завозе")

        # ── 12. Статусы заказа и возврат на склад ───────────────────────
        order_num = order["number"]
        async with SessionMaker() as session:
            db_order = await session.scalar(
                select(Order).where(Order.number == order_num))
            order_id = db_order.id

        r = await c.post(f"/api/admin/orders/{order_id}/status", headers=BH,
                         json={"status": O_PAID})
        check(r.status_code == 403, "Покупатель статус не меняет", r.status_code)

        r = await c.post(f"/api/admin/orders/{order_id}/status", headers=AH,
                         json={"status": O_DONE})
        check(r.status_code == 400, "Через голову статусы не перескакивают",
              r.json().get("detail"))

        r = await c.post(f"/api/admin/orders/{order_id}/status", headers=AH,
                         json={"status": O_CONFIRMED})
        check(r.json()["status"] == O_CONFIRMED, "Подтверждён")
        r = await c.post(f"/api/admin/orders/{order_id}/status", headers=AH,
                         json={"status": O_PAID})
        check(r.json()["status"] == O_PAID, "Оплачен")
        r = await c.post(f"/api/admin/orders/{order_id}/status", headers=AH,
                         json={"status": "shipped", "tracking": "KZ123456789"})
        check(r.json()["tracking"] == "KZ123456789", "Трек-номер сохранён")

        async with SessionMaker() as session:
            before = (await session.scalar(
                select(Variant).where(Variant.id == vs["S"]))).stock

        big_id = None
        async with SessionMaker() as session:
            db = await session.scalar(select(Order).where(Order.number == big["number"]))
            big_id = db.id
        r = await c.post(f"/api/admin/orders/{big_id}/status", headers=AH,
                         json={"status": O_CANCELED})
        check(r.json()["status"] == O_CANCELED, "Заказ отменён")
        async with SessionMaker() as session:
            after = (await session.scalar(
                select(Variant).where(Variant.id == vs["S"]))).stock
            check(after == before + 2, "Отменённые вещи вернулись на склад",
                  f"{before} → {after}")

        # ── 13. Сводка для панели ───────────────────────────────────────
        r = await c.get("/api/admin/summary", headers=AH)
        js = r.json()
        check(js["orders"]["done"] == 0 and js["orders"]["canceled"] == 1,
              "Заказы посчитаны", js["orders"])
        check(js["products"]["units"] >= 2, "Единицы на складе посчитаны",
              js["products"]["units"])

        r = await c.get("/api/admin/summary", headers=BH)
        check(r.status_code == 403, "Сводка закрыта от покупателя")

        r = await c.get("/api/orders/mine", headers=BH)
        check(len(r.json()["items"]) >= 2, "Свои заказы видны покупателю",
              len(r.json()["items"]))

        # ── 14. Самовывоз без адреса ────────────────────────────────────
        async with SessionMaker() as session:
            variant = await session.get(Variant, vs["S"])
            variant.stock = 5
            await session.commit()
            product = await session.scalar(select(Product))
            fresh = await product_service.load(session, product.id)
            await product_service.refresh(session, fresh)

        # у второго покупателя в корзине остался неудавшийся размер — чистим
        await c.delete("/api/cart", headers=OH)
        await c.post("/api/cart", headers=OH, json={"variant_id": vs["S"], "qty": 1})
        r = await c.post("/api/orders", headers=OH, json={
            "customer_name": "Данияр", "phone": "87019998877",
            "delivery": "pickup"})
        check(r.status_code == 200 and r.json()["delivery_price"] == 0,
              "Самовывоз без адреса и бесплатно", r.text[:120])

    return report()


sys.exit(asyncio.run(main()))
