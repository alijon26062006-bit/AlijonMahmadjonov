"""Вход на сайт: номер и код от бота, Google, привязка, права."""
import asyncio
import sys

from common import check, report


async def main():
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import delete, select

    from app.api.main import app
    from app.db.base import SessionMaker
    from app.db.models import AuthCode, User
    from app.services import accounts, auth_code

    async with SessionMaker() as s:
        await s.execute(delete(AuthCode))
        await s.execute(delete(User).where(User.phone.in_(
            ["+77010000001", "+77010000002"])))
        await s.execute(delete(User).where(User.google_sub == "google-123"))
        await s.execute(delete(User).where(
            User.tg_id.in_([900001, 900002, 7418217143])))
        await s.execute(delete(User).where(User.phone == "+77010000009"))
        await s.commit()

    # ── нормализация номера ──
    n = auth_code.normalize_phone
    check(n("8 701 000 00 01") == "+77010000001", "восьмёрка → +7")
    check(n("+7 (701) 000-00-01") == "+77010000001", "скобки и дефисы")
    check(n("7010000001") == "+77010000001", "без кода страны")
    check(n("12345") is None, "мусор отвергнут")
    check(n("+9 999 999 99 99") is None, "чужая страна отвергнута")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        # ── заявка на вход ──
        r = await c.post("/api/auth/phone/request", json={"phone": "8 701 000 00 01"})
        check(r.status_code == 200, "заявка принята", r.text[:80])
        req = r.json()
        check(req["phone"] == "+77010000001", "номер нормализован в ответе")
        check("start=c_" in req["link"], "ссылка ведёт в бота", req["link"][-20:])
        key = req["key"]

        r = await c.post("/api/auth/phone/request", json={"phone": "нет"})
        check(r.status_code == 400, "кривой номер отвергнут")

        # ── пока бот не подтвердил, вкладка ждёт ──
        r = await c.get("/api/auth/phone/status", params={"key": key})
        check(r.json()["status"] == "waiting", "до подтверждения — ожидание")

        # ── бот сверяет контакт ──
        async with SessionMaker() as s:
            entry = await auth_code.by_key(s, key)
            try:
                await auth_code.confirm(s, entry, contact_phone="+77019999999",
                                        tg_id=900001)
                check(False, "чужой номер должен отвергаться")
            except auth_code.AuthError:
                check(True, "чужой номер отвергнут")
            code = await auth_code.confirm(s, entry,
                                           contact_phone="87010000001",
                                           tg_id=900001)
        check(len(code) == 6 and code.isdigit(), "код из шести цифр", code)

        # ── неверный код ──
        r = await c.post("/api/auth/phone/verify",
                         json={"key": key, "code": "000000" if code != "000000"
                               else "111111"})
        check(r.status_code == 400, "неверный код не пускает")

        # ── верный код ──
        r = await c.post("/api/auth/phone/verify", json={"key": key, "code": code})
        check(r.status_code == 200, "верный код пускает", r.text[:120])
        data = r.json()
        token = data["access_token"]
        check(data["user"]["phone"] == "+77010000001", "номер в профиле")
        check(data["user"]["tg_linked"] is True, "Telegram привязан заодно")

        # ── код одноразовый ──
        r = await c.post("/api/auth/phone/verify", json={"key": key, "code": code})
        check(r.status_code == 400, "повторный вход тем же кодом закрыт")

        # ── профиль ──
        h = {"Authorization": f"Bearer {token}"}
        r = await c.get("/api/auth/me", headers=h)
        check(r.status_code == 200, "профиль доступен по токену")
        r = await c.patch("/api/auth/me", headers=h,
                          json={"name": "  Алижон  ", "notify_email": False,
                                "onboarding_done": True})
        me = r.json()
        check(me["name"] == "Алижон", "имя обрезано по краям", repr(me["name"]))
        check(me["notify_email"] is False, "переключатель почты сохранён")
        check(me["onboarding_done"] is True, "знакомство отмечено пройденным")

        # ── вход без цифр: бот подтвердил — вкладка впускает ──
        r = await c.post("/api/auth/phone/request", json={"phone": "+77010000002"})
        key2 = r.json()["key"]
        async with SessionMaker() as s:
            entry = await auth_code.by_key(s, key2)
            await auth_code.confirm(s, entry, contact_phone="+77010000002",
                                    tg_id=900002)
        r = await c.get("/api/auth/phone/status", params={"key": key2})
        check(r.json()["status"] == "confirmed", "подтверждение впускает без кода")
        check("access_token" in r.json(), "токен выдан")
        r = await c.get("/api/auth/phone/status", params={"key": key2})
        check(r.json()["status"] == "waiting", "заявка использована один раз")

        # ── лимит запросов ──
        limited = False
        for _ in range(8):
            r = await c.post("/api/auth/phone/request",
                             json={"phone": "+77010000002"})
            if r.status_code == 400:
                limited = True
                break
        check(limited, "частые запросы кода ограничены")

        # ── Google ──
        async with SessionMaker() as s:
            user = await accounts.login_with_google(
                s, {"sub": "google-123", "email": "Test@Gmail.com",
                    "name": "Гость", "picture": "https://x/y.png"})
            check(user.email == "test@gmail.com", "почта приведена к нижнему регистру")
            check(user.tg_id is None, "Google-аккаунт живёт без Telegram")
            again = await accounts.login_with_google(
                s, {"sub": "google-123", "email": "test@gmail.com"})
            check(again.id == user.id, "второй вход не создаёт второй аккаунт")

            # привязка бота к Google-аккаунту
            linked = await accounts.link_telegram(s, again, tg_id=7418217143,
                                                  username="owner", name="Хозяин")
            check(linked.tg_id == 7418217143, "Telegram привязан")
            check(linked.is_admin is True, "права взяты из ADMIN_IDS")

            # чужой Telegram не переезжает на второй аккаунт
            other = await accounts.login_with_phone(s, "+77010000009")
            await accounts.link_telegram(s, other, tg_id=7418217143,
                                         username=None, name=None)
            check(other.tg_id != 7418217143, "занятый Telegram не отбирается")
            await s.delete(other)
            await s.commit()

    return report()


sys.exit(asyncio.run(main()))
