"""Общее для проверок: настройки, счётчик и вход по номеру.

Проверки идут на настоящих PostgreSQL и Redis — заглушки прячут ровно те
ошибки, ради которых всё и затевается: блокировки строк, уникальные
индексы, поведение JSONB.
"""
import os
import sys

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://bozor:bozor@localhost:5432/shop")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("JWT_SECRET", "test-secret-key-at-least-32-chars")
os.environ.setdefault("BOT_TOKEN", "123456:TEST")
os.environ.setdefault("ADMIN_IDS", "7418217143")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test.apps.googleusercontent.com")
os.environ.setdefault("FREE_DELIVERY_FROM", "30000")
os.environ.setdefault("DELIVERY_CITY_PRICE", "1500")
os.environ.setdefault("PICKUP_ADDRESS", "Алматы, Сейфуллина 500")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_state = {"ok": 0, "fail": 0}


def check(cond, name: str, extra: str = "") -> None:
    if cond:
        _state["ok"] += 1
        print(f"OK   {name} {extra}")
    else:
        _state["fail"] += 1
        print(f"FAIL {name} {extra}")


def report() -> int:
    print(f"\n{'─' * 46}\nПройдено {_state['ok']}, провалено {_state['fail']}")
    return 1 if _state["fail"] else 0


async def login(client, phone: str, tg_id: int, name: str = "") -> str:
    """Проходит весь путь входа и возвращает токен.

    Повторяет ровно то, что делает живой человек: заявка на сайте, кнопка
    «отправить номер» в боте, шесть цифр обратно на сайт.
    """
    from app.db.base import SessionMaker
    from app.services import auth_code

    response = await client.post("/api/auth/phone/request", json={"phone": phone})
    key = response.json()["key"]
    async with SessionMaker() as session:
        entry = await auth_code.by_key(session, key)
        code = await auth_code.confirm(session, entry, contact_phone=phone,
                                       tg_id=tg_id)
    response = await client.post("/api/auth/phone/verify",
                                 json={"key": key, "code": code})
    data = response.json()
    if name and data.get("access_token"):
        await client.patch("/api/auth/me", json={"name": name},
                           headers={"Authorization":
                                    f"Bearer {data['access_token']}"})
    return data["access_token"]
