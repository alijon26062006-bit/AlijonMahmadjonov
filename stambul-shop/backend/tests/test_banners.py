"""Баннеры: срок показа, очередь, права, витрина."""
import asyncio
import hashlib
import hmac
import sys

from common import check, login, report

ADMIN_TG = 7418217143
ADMIN_PHONE = "+77010000401"


def signed(n: int) -> dict:
    """Загруженное фото подписывается сервером — подделываем ту же подпись."""
    from app.config import get_settings
    photo = {"file_id": f"file{n}", "thumb_file_id": f"thumb{n}",
             "thumb_w": 640, "file_unique_id": f"uniq{n}"}
    msg = f'{photo["file_id"]}|{photo["file_unique_id"]}'.encode()
    photo["sig"] = hmac.new(get_settings().jwt_secret.encode(), msg,
                            hashlib.sha256).hexdigest()
    return photo


async def main():
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import delete

    from app.api.main import app
    from app.db.base import SessionMaker
    from app.db.models import Banner

    async with SessionMaker() as s:
        await s.execute(delete(Banner))
        await s.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        token = await login(c, ADMIN_PHONE, ADMIN_TG, "Владелец")
        AH = {"Authorization": f"Bearer {token}"}

        r = await c.get("/api/banners")
        check(r.json()["items"] == [], "Пока баннеров нет, витрина их не просит")

        # ── создание ──
        r = await c.post("/api/admin/banners", headers=AH, json={
            "photo": signed(1), "title": "Зимние куртки", "days": 7,
            "link": "/catalog?category=women_clothes", "button_text": "Смотреть"})
        check(r.status_code == 200, "Баннер создаётся", r.text[:100])
        first = r.json()
        check(first["days_left"] == 6 or first["days_left"] == 7,
              "Срок показа посчитан", str(first["days_left"]))
        check(first["photo"].endswith("/photo"), "Ссылка на картинку выдана")

        r = await c.post("/api/admin/banners", headers=AH, json={
            "photo": signed(2), "title": "Обувь", "days": 0})
        second = r.json()
        check(second["days_left"] is None, "Ноль дней — значит без срока")

        # ── чужую фотографию не подсунуть ──
        fake = signed(3)
        fake["sig"] = "0" * 64
        r = await c.post("/api/admin/banners", headers=AH,
                         json={"photo": fake, "title": "Чужое"})
        check(r.status_code == 400, "Неподписанная фотография отвергнута")

        # ── очередь ──
        r = await c.get("/api/banners")
        titles = [b["title"] for b in r.json()["items"]]
        check(titles == ["Зимние куртки", "Обувь"], "Порядок как заводили",
              ", ".join(titles))

        r = await c.post(f"/api/admin/banners/{second['id']}/move?direction=up",
                         headers=AH)
        check(r.status_code == 200, "Порядок меняется", r.text[:80])
        r = await c.get("/api/banners")
        titles = [b["title"] for b in r.json()["items"]]
        check(titles == ["Обувь", "Зимние куртки"], "Второй поднялся наверх",
              ", ".join(titles))

        # ── скрытие ──
        await c.patch(f"/api/admin/banners/{first['id']}", headers=AH,
                      json={"is_active": False})
        r = await c.get("/api/banners")
        check(len(r.json()["items"]) == 1, "Скрытый на витрине не показывается")
        r = await c.get("/api/admin/banners", headers=AH)
        check(len(r.json()["items"]) == 2, "Но в панели виден")

        # ── просроченный уходит сам ──
        async with SessionMaker() as s:
            from datetime import datetime, timedelta, timezone
            from sqlalchemy import select
            b = await s.scalar(select(Banner).where(Banner.title == "Обувь"))
            b.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
            await s.commit()
        r = await c.get("/api/banners")
        check(r.json()["items"] == [],
              "Просроченный баннер снимается с витрины сам")
        r = await c.get("/api/admin/banners", headers=AH)
        expired = [b for b in r.json()["items"] if b["expired"]]
        check(len(expired) == 1, "В панели видно, что срок вышел")

        # ── продление ──
        await c.patch(f"/api/admin/banners/{second['id']}", headers=AH,
                      json={"days": 14})
        r = await c.get("/api/banners")
        check(len(r.json()["items"]) == 1, "Продлённый вернулся на витрину")

        # ── удаление ──
        r = await c.delete(f"/api/admin/banners/{first['id']}", headers=AH)
        check(r.status_code == 200, "Баннер удаляется")
        r = await c.get("/api/admin/banners", headers=AH)
        check(len(r.json()["items"]) == 1, "И его больше нет в списке")

        # ── права ──
        buyer = await login(c, "+77010000402", 810888, "Покупатель")
        BH = {"Authorization": f"Bearer {buyer}"}
        r = await c.get("/api/admin/banners", headers=BH)
        check(r.status_code == 403, "Покупатель в баннеры не ходит")
        r = await c.post("/api/admin/banners", headers=BH,
                         json={"photo": signed(9), "title": "Взлом"})
        check(r.status_code == 403, "И создать не может")

        from app.db.models import User
        async with SessionMaker() as s:
            await s.execute(delete(User).where(User.tg_id == 810888))
            await s.commit()

    return report()


sys.exit(asyncio.run(main()))
