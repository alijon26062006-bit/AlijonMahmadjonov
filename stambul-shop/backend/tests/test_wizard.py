"""Свои разделы и черновик от модели: то, что бот использует при заведении."""
import asyncio
import sys

from common import check, login, report

ADMIN_TG = 7418217143
ADMIN_PHONE = "+77010000301"


async def main():
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import delete

    from app.api.main import app
    from app.catalog.schemas import all_categories, get_category, groups
    from app.db.base import SessionMaker
    from app.db.models import CustomCategory
    from app.services import ai_vision
    from app.services import categories as cats

    # ── slug из русского названия ──
    check(cats.slugify("Спорттовары") == "sporttovary", "Русское название → slug",
          cats.slugify("Спорттовары"))
    check(cats.slugify("Товары для дома!!!") == "tovary_dlya_doma",
          "Знаки препинания не попадают в адрес",
          cats.slugify("Товары для дома!!!"))
    check(cats.slugify("   ") == "razdel", "Пустое название не ломает адрес")

    async with SessionMaker() as s:
        await s.execute(delete(CustomCategory))
        await s.commit()

        built_in = len(all_categories())
        made = await cats.create(s, "  Спорттовары  ")
        check(made.title == "Спорттовары", "Название обрезано по краям", made.title)
        check(made.slug == "sporttovary", "Адрес раздела читаемый", made.slug)
        check(len(all_categories()) == built_in + 1, "Раздел добавился к общим")
        check(get_category("sporttovary") is not None,
              "Свой раздел находится наравне со встроенными")
        check(len(made.size_scales) >= 1, "У своего раздела есть размерная линейка")

        again = await cats.create(s, "спорттовары")
        check(again.slug == made.slug, "Повтор названия не плодит разделы",
              again.slug)

        names = [g["title"] for g in groups()]
        check("Разное" in names, "Свои разделы живут в группе «Разное»",
              ", ".join(names))

        # встроенный раздел нельзя перебить своим
        collision = await cats.create(s, "shoes")
        check(collision.slug != "shoes", "Встроенный раздел не перезаписывается",
              collision.slug)

    # ── черновик от модели: чистим то, чему нельзя верить ──
    draft = ai_vision.clean({
        "title": "  Мужские   кроссовки  ",
        "category": "выдуманный_раздел",
        "brand": "NIKE",
        "color": "чёрный матовый",
        "description": "x" * 3000,
        "uncertain": ["material", "brand", 1, None] + ["x"] * 20,
        "material": None,
    })
    check(draft["title"] == "Мужские кроссовки", "Лишние пробелы убраны",
          draft["title"])
    check(draft["category"] == "", "Несуществующий раздел отброшен")
    check(draft["color"] == "Чёрный", "Цвет приведён к списку каталога",
          draft["color"])
    check(len(draft["description"]) <= 1200, "Описание обрезано",
          str(len(draft["description"])))
    check(len(draft["uncertain"]) <= 8, "Список сомнений ограничен",
          str(len(draft["uncertain"])))
    check(draft["material"] == "", "Нестроковое значение не попадает в карточку")

    real = ai_vision.clean({"category": "shoes", "color": "Белый"})
    check(real["category"] == "shoes", "Настоящий раздел проходит")
    check(real["color"] == "Белый", "Цвет из списка проходит как есть")

    # ── товар в своём разделе живёт как обычный ──
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        token = await login(c, ADMIN_PHONE, ADMIN_TG, "Владелец")
        AH = {"Authorization": f"Bearer {token}"}

        r = await c.get("/api/categories")
        titles = [x["title"] for g in r.json()["groups"] for x in g["categories"]]
        check("Спорттовары" in titles, "Свой раздел виден на витрине")

        r = await c.post("/api/admin/products", headers=AH, json={
            "category": "sporttovary", "title": "Скакалка скоростная",
            "description": "Проверочный товар"})
        check(r.status_code == 200, "Товар заводится в своём разделе",
              r.text[:100])
        pid = r.json()["id"]

        r = await c.put(f"/api/admin/products/{pid}/variants", headers=AH,
                        json={"variants": [{"size": "", "color": "Чёрный",
                                        "price": 3900, "stock": 4}]})
        check(r.status_code == 200, "Вариант добавляется", r.text[:100])

        r = await c.get("/api/products?category=sporttovary")
        check(r.status_code == 200, "Каталог фильтруется по своему разделу")

        r = await c.get("/api/categories/sporttovary")
        js = r.json()
        check(r.status_code == 200 and js["title"] == "Спорттовары",
              "Схема своего раздела отдаётся", r.text[:80])

    # ── полоса выполнения ──
    from app.bot.handlers.add_product import Progress

    class FakeMessage:
        def __init__(self):
            self.texts = []

        async def edit_text(self, text, **kw):
            self.texts.append(text)

        async def delete(self):
            self.texts.append("<удалено>")

    note = FakeMessage()
    bar = Progress(note)
    await bar.start()
    await bar.set(30, "Убираю фон")
    await bar.set(10, "Шаг назад")          # проценты не должны падать
    await bar.set(100, "Готово")
    await bar.finish()

    check(any("30%" in t for t in note.texts), "Полоса показывает проценты")
    check(not any("10%" in t for t in note.texts),
          "Проценты не откатываются назад")
    check(any("100%" in t for t in note.texts), "Доходит до ста")
    check(note.texts[-1] == "<удалено>", "В конце сообщение убирается")
    check(all(" с" in t for t in note.texts if t != "<удалено>"),
          "Рядом тикают секунды — видно, что не зависло")

    return report()


sys.exit(asyncio.run(main()))
