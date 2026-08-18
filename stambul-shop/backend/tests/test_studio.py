"""Подготовка фотографий: стиль, выбор фона, настройки, переключение версии."""
import asyncio
import io
import sys

from common import check, login, report

ADMIN_TG = 7418217143
ADMIN_PHONE = "+77010000201"


def sample(colour, size=(600, 800)):
    from PIL import Image, ImageDraw
    image = Image.new("RGB", size, (150, 120, 90))
    ImageDraw.Draw(image).rounded_rectangle(
        (size[0] // 5, size[1] // 5, size[0] * 4 // 5, size[1] * 4 // 5),
        radius=30, fill=colour)
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=92)
    return buffer.getvalue()


async def main():
    from httpx import ASGITransport, AsyncClient
    from PIL import Image
    from sqlalchemy import delete

    from app.api.main import app
    from app.db.base import SessionMaker
    from app.db.models import ProductPhoto, User
    from app.imaging import pipeline
    from app.imaging.style import BACKGROUNDS, STYLE_VERSION
    from app.services import product_service, settings_store

    # ── стиль каталога ──
    check(STYLE_VERSION >= 1, "У стиля каталога есть версия", str(STYLE_VERSION))
    check(len(BACKGROUNDS) == 3, "Фонов ровно три, не больше",
          ", ".join(BACKGROUNDS))
    check(all(len(set(b.rgb)) == 1 for b in BACKGROUNDS.values()),
          "Все фоны нейтральные: без цветного оттенка")

    # ── выбор фона под товар ──
    def fake_cutout(image):
        out = Image.new("RGBA", image.size, (0, 0, 0, 0))
        w, h = image.size
        box = (w // 5, h // 5, w * 4 // 5, h * 4 // 5)
        out.paste(image.convert("RGBA").crop(box), box[:2])
        return out

    pipeline._cutout = fake_cutout

    dark = pipeline.compose(sample((16, 16, 18)))
    mid = pipeline.compose(sample((120, 95, 70)))
    light = pipeline.compose(sample((250, 250, 248)))
    check(dark.background == "light", "Тёмному товару — светлый фон",
          dark.background)
    check(mid.background == "very_light", "Среднему товару — самый светлый фон",
          mid.background)
    check(light.background == "soft_gray",
          "Очень светлому — сероватый, иначе растворится", light.background)

    check(dark.width == 1200 and dark.height == 1500,
          "Формат кадра одинаков у всех", f"{dark.width}x{dark.height}")
    check(dark.style_version == STYLE_VERSION, "Версия стиля записана в результат")

    forced = pipeline.compose(sample((16, 16, 18)), background="soft_gray")
    check(forced.background == "soft_gray", "Выбор владельца сильнее автоматики")

    a = Image.open(io.BytesIO(dark.data))
    b = Image.open(io.BytesIO(light.data))
    check(a.size == b.size, "Все карточки одного размера", str(a.size))

    corner = a.getpixel((5, 5))
    check(max(corner) - min(corner) <= 2 and corner[0] > 200,
          "Углы кадра — чистый нейтральный фон", str(corner))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        token = await login(c, ADMIN_PHONE, ADMIN_TG, "Владелец")
        AH = {"Authorization": f"Bearer {token}"}

        # ── настройки: ключ не возвращается наружу ──
        r = await c.patch("/api/admin/settings", headers=AH,
                          json={"ai_provider": "removebg",
                                "ai_api_key": "secret-key-1234"})
        data = r.json()
        check(r.status_code == 200, "Настройки сохраняются", r.text[:80])
        check(data["ai_key_set"] is True, "Признак «ключ задан» виден")
        check("secret" not in r.text, "Сам ключ наружу не уходит")
        check(data["ai_key_hint"] == "••••1234", "Виден только хвост ключа",
              data["ai_key_hint"])

        async with SessionMaker() as s:
            stored = await settings_store.get(s, "ai_api_key")
        check(stored == "secret-key-1234", "На сервере ключ сохранён целиком")

        r = await c.patch("/api/admin/settings", headers=AH,
                          json={"ai_provider": "магия"})
        check(r.status_code == 400, "Неизвестный способ обработки отвергнут")

        # ── фотография товара ──
        async with SessionMaker() as s:
            await s.execute(delete(ProductPhoto))
            product = await product_service.create(
                s, category_slug="shoes", title="Кроссовки для проверки")
            photo = ProductPhoto(product_id=product.id, file_id="demo",
                                 file_unique_id="demo1", position=0)
            s.add(photo)
            await s.commit()
            await s.refresh(photo)
            photo_id, public_id = photo.id, product.public_id

        r = await c.get(f"/api/admin/products/{public_id}/photos", headers=AH)
        js = r.json()
        check(r.status_code == 200 and len(js["items"]) == 1,
              "Фотографии товара видны в панели", r.text[:80])
        check(js["items"][0]["has_processed"] is False,
              "Обработанной версии пока нет")
        check(len(js["backgrounds"]) == 3, "Панель знает про три фона")

        r = await c.post(f"/api/admin/photos/{photo_id}/version", headers=AH,
                         json={"use_processed": True})
        check(r.status_code == 400, "Без обработки переключаться не на что")

        async with SessionMaker() as s:
            p = await s.get(ProductPhoto, photo_id)
            p.proc_file_id = "demo-proc"
            p.proc_file_unique_id = "demo1p"
            p.background = "light"
            p.style_version = STYLE_VERSION
            p.processing = "ready"
            await s.commit()

        r = await c.post(f"/api/admin/photos/{photo_id}/version", headers=AH,
                         json={"use_processed": True})
        check(r.json()["use_processed"] is True, "Переключились на обработанную")

        r = await c.post(f"/api/admin/photos/{photo_id}/version", headers=AH,
                         json={"use_processed": False})
        check(r.json()["use_processed"] is False, "И обратно на оригинал")

        async with SessionMaker() as s:
            p = await s.get(ProductPhoto, photo_id)
        check(p.file_id == "demo" and p.proc_file_id == "demo-proc",
              "Оригинал на месте после всех переключений")

        # ── ретушь: задание и приёмка результата ──
        from app.imaging import fashion
        from app.services import ai_check

        prompt = fashion.build_prompt(kind="clothes", reshape=True,
                                      background="soft_gray",
                                      note="рукав справа загнулся")
        check("источник истины" in prompt,
              "В задании сказано, что оригинал — источник истины")
        check("не придумывай" in prompt, "Прямо запрещено выдумывать невидимое")
        check("плиссе" in prompt, "Складки-часть-модели названы отдельно")
        check("рукав справа загнулся" in prompt,
              "Пожелание владельца попадает в задание")
        check("229" in prompt, "Цвет фона задан числами", "soft_gray")

        plain = fashion.build_prompt(kind="shoes", reshape=True,
                                     background="light")
        check("манекен" in plain.lower(),
              "Обуви объясняют, что манекен не нужен")
        check("плиссе" not in plain, "Обуви не рассказывают про плиссе одежды")

        check(fashion.kind_for("women_clothes") == "clothes", "Платье — одежда")
        check(fashion.kind_for("shoes") == "shoes", "Обувь опознана")
        check(fashion.kind_for("accessories") == "bag", "Сумка опознана")
        check(fashion.kind_for("dishes") == "home", "Посуда — для дома")

        strict = ai_check.clean({"severity": "major", "same_product": True,
                                 "differences": ["пропал логотип"]})
        check(strict["same_product"] is False,
              "При серьёзном расхождении «тот же товар» не проходит")
        check(ai_check.status_of(strict) == "review",
              "Серьёзное расхождение уводит карточку на проверку")
        check(ai_check.status_of(ai_check.clean({"severity": "none"})) == "ok",
              "Без расхождений карточку можно показывать")
        check(ai_check.status_of(ai_check.clean({"severity": "чепуха"}))
              == "review",
              "Непонятный ответ сверки трактуется в пользу осторожности")

        buyer = await login(c, "+77010000202", 810777, "Покупатель")
        r = await c.get("/api/admin/settings",
                        headers={"Authorization": f"Bearer {buyer}"})
        check(r.status_code == 403, "Настройки закрыты от покупателя")

        async with SessionMaker() as s:
            await s.execute(delete(User).where(User.tg_id == 810777))
            await s.commit()

    return report()


sys.exit(asyncio.run(main()))
