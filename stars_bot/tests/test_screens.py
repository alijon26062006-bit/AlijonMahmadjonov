"""Картинки экранов и Glory только СНГ за 30 сомони."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_fixture  # noqa: F401

from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import DeleteMessage, EditMessageText, SendMessage

from app import db, runtime, screens
from app.middlewares.photo_text import PhotoTextGuard
from app.services import donatix as dx

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  — {detail}" if detail else ""))


class Msg:
    """Сообщение понарошку: помнит, что с ним сделали."""

    def __init__(self, photo=False):
        self.photo = ["p"] if photo else None
        self.log = []

    async def answer(self, text, **kw):
        self.log.append(("answer", text))

    async def answer_photo(self, photo, caption="", **kw):
        self.log.append(("photo", photo, caption))

    async def edit_text(self, text, **kw):
        self.log.append(("edit_text", text))

    async def edit_media(self, media, **kw):
        self.log.append(("edit_media", media.media, media.caption))

    async def delete(self):
        self.log.append(("delete",))


class Call:
    def __init__(self, message):
        self.message = message


async def run(conn) -> None:
    # ---- нет картинки — всё как раньше
    m = Msg()
    await screens.show(Call(m), "текст", None, keys=("games",))
    check("без картинки — обычная правка текста", m.log == [("edit_text", "текст")], str(m.log))

    await runtime.set_value(conn, "img:games", "FILE_GAMES")
    await runtime.set_value(conn, "img:fam:free_fire", "FILE_FF")

    m = Msg()
    await screens.show(Call(m), "игры", None, keys=("games",))
    check("текстовый экран → удаляем и шлём с картинкой",
          m.log == [("delete",), ("photo", "FILE_GAMES", "игры")], str(m.log))

    m = Msg(photo=True)
    await screens.show(Call(m), "Free Fire ID", None,
                       keys=("game:free_fire_id", "fam:free_fire"))
    check("у региона нет своей — общая картинка игры, заменой фото",
          m.log == [("edit_media", "FILE_FF", "Free Fire ID")], str(m.log))

    await runtime.set_value(conn, "img:game:free_fire_id", "FILE_FF_ID")
    m = Msg(photo=True)
    await screens.show(Call(m), "Free Fire ID", None,
                       keys=("game:free_fire_id", "fam:free_fire"))
    check("у региона своя картинка — она", m.log[0][1] == "FILE_FF_ID", str(m.log))

    m = Msg()
    await screens.show(m, "/start", None, keys=("games",))
    check("на /start — фото с подписью", m.log == [("photo", "FILE_GAMES", "/start")])

    m = Msg()
    await screens.show(Call(m), "x" * 1500, None, keys=("games",))
    check("длинный текст — без картинки (лимит подписи)", m.log[0][0] == "edit_text")

    # ---- с картинки на текстовый экран: правка текста → новое сообщение
    calls = []

    class Bot:
        async def __call__(self, method):
            calls.append(type(method).__name__)
            return "sent"

    async def make_request(bot, method):
        raise TelegramBadRequest(method=method,
                                 message="Bad Request: there is no text in the message to edit")

    result = await PhotoTextGuard()(make_request, Bot(),
                                    EditMessageText(chat_id=1, message_id=5, text="профиль"))
    check("правка текста у фото → удалили и прислали текст",
          calls == ["DeleteMessage", "SendMessage"] and result == "sent", str(calls))

    async def other(bot, method):
        raise TelegramBadRequest(method=method, message="Bad Request: message to edit not found")

    try:
        await PhotoTextGuard()(other, Bot(), EditMessageText(chat_id=1, message_id=5, text="x"))
        check("другие ошибки не трогаем", False)
    except TelegramBadRequest:
        check("другие ошибки не трогаем", True)

    # ---- Glory: только Россия, клиенту — «СНГ», 30 сомони
    async def fake(method, path, body=None):
        return {"ok": True, "items": [
            {"id": "ru", "name": "Russia", "price_usd": "1.8000"},
            {"id": "pe", "name": "Peru", "price_usd": "1.0000"},
            {"id": "bd", "name": "Bangladesh", "price_usd": "1.0000"}]}

    dx._call = fake
    await runtime.set_value(conn, "usd_rate_diram", "1100")
    items = await dx.regions(fresh=True)
    check("клиенту только один регион", len(items) == 1, str([i["name"] for i in items]))
    check("назван «СНГ»", items and items[0]["name"] == "СНГ")
    check("цена 30 сомони", items and items[0]["price"] == 30_00, str(items and items[0]["price"]))
    check("себестоимость по курсу посчитана", items and items[0]["cost"] == 19_80,
          str(items and items[0]["cost"]))
    everything = await dx.regions(everything=True)
    check("в панели видны все, отмечено, какие показываем",
          [r["shown"] for r in everything] == [True, False, False])
    await runtime.set_value(conn, "glory_regions", "")
    check("пустая настройка — все регионы", len(await dx.regions()) == 3)

    # ---- панель: загрузка картинки
    from app.handlers import panel

    class User:
        id, username, first_name = 111, "adm", "A"

    class Photo:
        file_id = "NEW_MAIN"

    class AdminMsg(Msg):
        def __init__(self):
            super().__init__()
            self.from_user = User()
            self.photo = [Photo()]

    state = FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=111, user_id=111))
    await state.set_state(panel.Panel.image)
    await state.update_data(image_key="main")
    await panel.on_image(AdminMsg(), state, conn)
    check("картинка главного экрана сохранена", screens.image("main") == "NEW_MAIN")


async def main() -> None:
    for sfx in ("", "-wal", "-shm"):
        Path(str(db.settings.db_file) + sfx).unlink(missing_ok=True)
    conn = await db.connect()
    try:
        await db.init(conn)
        await runtime.load(conn)
        await run(conn)
    finally:
        await conn.close()
    print(f"\n{'=' * 52}\nПройдено: {len(PASS)}   Провалено: {len(FAIL)}")
    if FAIL:
        print("ПРОВАЛЫ:", ", ".join(FAIL))
    sys.exit(1 if FAIL else 0)


asyncio.run(main())
