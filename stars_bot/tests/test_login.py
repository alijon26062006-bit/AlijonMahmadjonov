"""Вход юзербота в Telegram: неверный код, обрыв связи, облачный пароль."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_fixture  # noqa: F401

from telethon import errors

from app.userbot import login

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  — {detail}" if detail else ""))


class Sent:
    def __init__(self, n):
        self.phone_code_hash = f"hash{n}"


class Me:
    username, id, first_name = "owner", 1, "Владелец"


class FakeClient:
    """Telegram понарошку: код 12345, по желанию — пароль и обрывы."""

    def __init__(self, *, password=None, drop_after_first=False, expire_first=False,
                 authorized=False):
        self.password = password
        self.drop_after_first = drop_after_first
        self.expire_first = expire_first
        self.authorized = authorized
        self.connected = False
        self.sends = 0
        self.sign_ins: list[dict] = []
        self.need_password = False

    def is_connected(self):
        return self.connected

    async def connect(self):
        self.connected = True

    async def is_user_authorized(self):
        return self.authorized

    async def get_me(self):
        return Me()

    async def send_code_request(self, phone):
        self.sends += 1
        self.phone = phone
        return Sent(self.sends)

    async def sign_in(self, phone=None, code=None, *, password=None,
                      phone_code_hash=None):
        if not self.connected:
            raise ConnectionError("нет связи")
        self.sign_ins.append({"code": code, "hash": phone_code_hash,
                              "password": password})
        if password is not None:
            if password == self.password:
                return Me()
            raise errors.PasswordHashInvalidError(request=None)
        if phone_code_hash is None:
            raise ValueError("You also need to provide a phone_code_hash.")
        if self.expire_first and self.sends == 1:
            raise errors.PhoneCodeExpiredError(request=None)
        if code != "12345":
            if self.drop_after_first:
                self.connected = False      # сервер закрыл соединение
            raise errors.PhoneCodeInvalidError(request=None)
        if self.password:
            raise errors.SessionPasswordNeededError(request=None)
        return Me()


def feeder(*answers):
    queue = list(answers)
    return lambda prompt="": queue.pop(0) if queue else ""


async def run() -> None:
    check("номер с пробелами чистится", login.clean_phone("+992 11 117-89 99") == "+992111178999")
    check("код с пробелами чистится", login.clean_code(" 12 345 ") == "12345")

    said: list[str] = []
    client = FakeClient(drop_after_first=True)
    me = await login.sign_in_flow(client, ask=feeder("+992 00 000 0000", "54321", "12 345"),
                                  ask_secret=feeder(), say=said.append)
    check("неверный код, обрыв связи, верный код — вход прошёл", me is not None, str(said[-2:]))
    check("хэш кода не потерялся после обрыва",
          all(s["hash"] == "hash1" for s in client.sign_ins), str(client.sign_ins))
    check("неверный код объяснён по-русски", any("не подошёл" in s for s in said))
    check("номер ушёл в Telegram без пробелов", client.phone == "+992000000000")

    said.clear()
    client = FakeClient(password="секрет")
    me = await login.sign_in_flow(client, ask=feeder("+99200000000", "12345"),
                                  ask_secret=feeder("не тот", "секрет"), say=said.append)
    check("облачный пароль спрошен и принят", me is not None and
          client.sign_ins[-1]["password"] == "секрет", str(client.sign_ins))
    check("неверный пароль объяснён", any("Пароль не подошёл" in s for s in said))

    said.clear()
    client = FakeClient(expire_first=True)
    me = await login.sign_in_flow(client, ask=feeder("+99200000000", "12345", "12345"),
                                  ask_secret=feeder(), say=said.append)
    check("устаревший код — новый запрошен сам", me is not None and client.sends == 2,
          f"отправок: {client.sends}")
    check("и код проверяется с новым хэшем", client.sign_ins[-1]["hash"] == "hash2")

    said.clear()
    client = FakeClient()
    me = await login.sign_in_flow(client, ask=feeder("+99200000000", *["1"] * 9),
                                  ask_secret=feeder(), say=said.append)
    check("девять неверных кодов — отказ без падения", me is None, str(said[-1:]))
    check("код запрашивался не больше трёх раз", client.sends == login.SENDS)

    client = FakeClient(authorized=True)
    me = await login.sign_in_flow(client, ask=feeder(), ask_secret=feeder(), say=said.append)
    check("живой сеанс — код не нужен", me is not None and client.sends == 0)


asyncio.run(run())
print(f"\n{'=' * 52}\nПройдено: {len(PASS)}   Провалено: {len(FAIL)}")
if FAIL:
    print("ПРОВАЛЫ:", ", ".join(FAIL))
sys.exit(1 if FAIL else 0)
