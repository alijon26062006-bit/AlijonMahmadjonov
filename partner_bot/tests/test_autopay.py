"""Автоплатёж по уведомлению банка: проверки по списку из задачи.

Запуск: python tests/test_autopay.py
Номера карт и счетов выдуманы.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_fixture  # noqa: F401,E402

from app import db, runtime  # noqa: E402
from app.config import settings  # noqa: E402
from app.userbot import parser, processor  # noqa: E402

settings.tg_api_id, settings.tg_api_hash, settings.bank_bot = 1, "x" * 32, "bank_test_bot"

SOURCE = "bank_test_bot"
A, B = 95001, 95002          # клиенты
PANEL_ADMIN = 95999          # админ, добавленный из панели
PASS, FAIL = [], []
_msg = iter(range(70_000, 80_000))


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  — {detail}" if detail else ""))


class FakeBot:
    def __init__(self):
        self.sent, self.edited = [], []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))

    async def edit_message_text(self, chat_id, message_id, text, **kw):
        self.edited.append((chat_id, message_id, text))

    async def edit_message_reply_markup(self, chat_id, message_id, **kw):
        self.edited.append((chat_id, message_id, "<кнопки убраны>"))

    def clear(self):
        self.sent.clear()
        self.edited.clear()


def notice(amount: str, kod: str = "", sender: str = "9990000***1111", **extra) -> str:
    lines = ["Zachislenie", f"Summa {amount} TJS", "Komis 0.00 TJS", f"Zachislenie {amount} TJS",
             "Data 19:40 15.09.26", f"Otpravitel {sender}", f"Kod {kod or next(_msg)}",
             "Karta 9999000011112222", "Balans 3 686.07 TJS"]
    if extra.get("comment"):
        lines.append(f"Comment {extra['comment']}")
    return "\n".join(lines)


async def handle(conn, bot, text):
    return await processor.handle(conn, bot, source=SOURCE, message_id=next(_msg), text=text)


async def fresh(conn):
    """Чистый лист: прошлые заявки и платежи не мешают следующей проверке."""
    await conn.execute("DELETE FROM deposits")
    await conn.execute("DELETE FROM bank_payments")
    await conn.execute("DELETE FROM bank_senders")
    await conn.commit()


async def balance(conn, uid):
    return (await db.get_user(conn, uid)).balance


async def dep(conn, uid, amount, method="Перевод на карту"):
    return await db.create_deposit(conn, user_id=uid, amount=amount, method=method,
                                   receipt_file_id="", reference="TOP1000")


# ───────────────────────────────────────────── парсер


def parsing() -> None:
    real = notice("617.00", kod="10000000001")
    n = parser.parse(real)
    check("пример банка → 61700 дирам", n.ok and n.amount == 61700, str(n.amount))
    check("сумма из Zachislenie", n.source_field == "zachislenie", n.source_field)
    check("карта — только «2222»", n.card_tail == "2222", n.card_tail)
    for word in ("Spisanie", "Perevod"):
        n = parser.parse(real.replace("Zachislenie", word, 1))
        check(f"{word} в первой строке → отказ", not n.ok, n.error)
    n = parser.parse("Zachislenie\nZachislenie -617.00 TJS")
    check("«Zachislenie -617.00» → отказ", not n.ok, n.error)
    n = parser.parse("Zachislenie\nSumma 100.00 TJS\nKomis 2.00 TJS")
    check("Summa 100 + Komis 2 без Zachislenie → отказ", not n.ok, n.error)
    n = parser.parse("Zachislenie\nSumma 100.43 TJS\nComment Сбербанк")
    check("Summa без строки Komis (Россия) → принято", n.ok and n.amount == 10043, n.error)
    n = parser.parse("Zachislenie\nZachislenie 617.00 TJS abc")
    check("«617.00 TJS abc» → отказ", not n.ok, n.error)
    check("«3 686,07» → 368607", parser.money("3 686,07") == 368607, str(parser.money("3 686,07")))
    n = parser.parse("Zachislenie\nZachislenie 617.00 TJS\nZachislenie 618.00 TJS")
    check("две разные суммы Zachislenie → отказ", not n.ok, n.error)
    check("пустое сообщение → отказ", not parser.parse("").ok)


# ───────────────────────────────────────────── копейки


async def kopecks(conn) -> None:
    await fresh(conn)
    hours = runtime.get_int("deposit_match_hours", 6)
    first = await db.free_amount(conn, 10000, hours)
    await dep(conn, A, first)
    second = await db.free_amount(conn, 10000, hours)
    check("две заявки по 100 → 100.01 и 100.02", (first, second) == (10001, 10002), f"{first}, {second}")

    await fresh(conn)
    await dep(conn, A, 1006)
    for amount in (1001, 1002, 1003, 1004, 1005):
        await dep(conn, B, amount)
    got = await db.free_amount(conn, 1000, hours)
    check("заявка 10.06 занимает хвост и для базы 10.00", got == 1007, str(got))


# ───────────────────────────────────────────── сопоставление


async def matching(conn, bot) -> None:
    await runtime.set_value(conn, "extra_admins", str(PANEL_ADMIN))

    # одна заявка на сумму
    await fresh(conn)
    d = await dep(conn, A, 10003)
    await db.set_deposit_screen(conn, d.id, A, 555)
    before = await balance(conn, A)
    bot.clear()
    text = notice("100.03", kod="5550001")
    r = await handle(conn, bot, text)
    check("одна заявка → зачислено", r.confirmed and await balance(conn, A) == before + 10003, r.status)
    check("экран реквизитов заменён",
          any(m == 555 and "Пардохт гирифта шуд" in t for _, m, t in bot.edited), str(bot.edited))
    told = {chat for chat, t in bot.sent if "автоматически" in t}
    check("написано всем админам — и из .env, и из панели",
          set(settings.admin_ids) | {PANEL_ADMIN} <= told, str(told))

    # то же уведомление второй раз
    now = await balance(conn, A)
    r = await processor.handle(conn, bot, source=SOURCE, message_id=next(_msg), text=text)
    check("то же уведомление (тот же код банка) → дубль", r.status == "duplicate", r.status)
    check("баланс не изменился", await balance(conn, A) == now)

    # две заявки, отправитель знаком
    await fresh(conn)
    await db.bind_sender(conn, "8880000***2222", B)
    da, db_ = await dep(conn, A, 20000), await dep(conn, B, 20000)
    r = await handle(conn, bot, notice("200.00", sender="8880000***2222"))
    check("две заявки, знакомый отправитель → его", r.confirmed and r.deposit_id == db_.id, r.status)
    check("чужая не тронута", (await db.get_deposit(conn, da.id)).status == db.DEP_PENDING)

    # две заявки, отправитель незнаком
    await fresh(conn)
    da, db_ = await dep(conn, A, 30000), await dep(conn, B, 30000)
    a0, b0 = await balance(conn, A), await balance(conn, B)
    r = await handle(conn, bot, notice("300.00", sender="7770000***3333"))
    check("незнакомый отправитель → ambiguous", r.status == db.BANK_AMBIGUOUS, r.status)
    check("ни одна не зачислена", (await balance(conn, A), await balance(conn, B)) == (a0, b0))

    # пришло 100.00 вместо 100.03
    await fresh(conn)
    d = await dep(conn, A, 10003)
    a0 = await balance(conn, A)
    r = await handle(conn, bot, notice("100.00"))
    check("100.00 при заявке 100.03 → зачислено 100.00",
          r.confirmed and await balance(conn, A) == a0 + 10000, str(await balance(conn, A) - a0))
    check("сумма заявки поправлена", (await db.get_deposit(conn, d.id)).amount == 10000)

    await fresh(conn)
    await dep(conn, A, 10003)
    await dep(conn, B, 10005)
    r = await handle(conn, bot, notice("100.00", sender="6660000***4444"))
    check("две заявки рядом → ambiguous", r.status == db.BANK_AMBIGUOUS, r.status)

    # владелец закрыл заявку раньше робота
    from app.handlers.admin import _resolve_deposit

    await fresh(conn)
    d = await dep(conn, A, 40001)
    await db.attach_receipt(conn, d.id, "receipt-race")
    a0 = await balance(conn, A)
    real = db.pending_deposits_for

    async def owner_first(conn_, amount, hours=6):
        rows = await real(conn_, amount, hours=hours)
        for row in rows:          # владелец нажал «Подтвердить» в ту же секунду
            await _resolve_deposit(conn_, bot, row.id, settings.admin_ids[0], approved=True)
        return rows

    db.pending_deposits_for = owner_first
    try:
        r = await handle(conn, bot, notice("400.01"))
    finally:
        db.pending_deposits_for = real
    check("закрыл владелец раньше → второй раз не начислено", await balance(conn, A) == a0 + 40001,
          str(await balance(conn, A) - a0))
    check("платёж помечен «закрыли раньше»", r.status == db.BANK_AMBIGUOUS and "раньше" in r.note, r.note)

    # заявка старше окна
    await fresh(conn)
    d = await dep(conn, A, 50001)
    old = (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat(timespec="seconds")
    await conn.execute("UPDATE deposits SET created_at = ? WHERE id = ?", (old, d.id))
    await conn.commit()
    r = await handle(conn, bot, notice("500.01"))
    check("заявка старше 6 часов не участвует", r.status == db.BANK_UNKNOWN, r.status)
    check("и осталась ждать", (await db.get_deposit(conn, d.id)).status == db.DEP_PENDING)

    # Россия: деньги раньше заявки
    from app import texts

    await fresh(conn)
    r = await handle(conn, bot, notice("107.43", comment="Сбербанк"))
    check("деньги из России без заявки → ждут", r.status == db.BANK_UNKNOWN, r.status)
    a0 = await balance(conn, A)
    d = await dep(conn, A, 10743, method=texts.RU_METHOD)
    done = await processor.claim_for_deposit(conn, bot, d)
    check("ввёл сумму из чека → зачислено сразу",
          done is not None and done.confirmed and await balance(conn, A) == a0 + 10743)


async def foreign_message() -> None:
    from app.userbot import runner

    class Msg:
        id, message = 1, "Zachislenie 999.00 TJS — привет, это личное"

        def __init__(self, sender_id, username):
            self.sender_id = sender_id
            self.sender = type("S", (), {"username": username})()

    records = []

    class Catch(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    catch = Catch()
    logging.getLogger().addHandler(catch)
    logging.getLogger("userbot").addHandler(catch)
    queue: asyncio.Queue = asyncio.Queue()
    try:
        took = runner.accept(Msg(777, "friend"), queue, 0, "bank_test_bot")
    finally:
        logging.getLogger().removeHandler(catch)
        logging.getLogger("userbot").removeHandler(catch)
    check("сообщение не от банковского бота → игнор", not took and queue.empty())
    check("и в журнал не попало", not records, str(records))
    check("от банковского бота — в очереди",
          runner.accept(Msg(5, "bank_test_bot"), queue, 0, "bank_test_bot") and queue.qsize() == 1)


# ───────────────────────────────────────────── «Я оплатил» без чека


class _Msg:
    def __init__(self, uid):
        self.texts, self.markups = [], []
        self.chat, self.message_id = type("C", (), {"id": uid})(), 7

    async def edit_text(self, text, reply_markup=None, **kw):
        self.texts.append(text)
        self.markups.append(reply_markup)


class _Call:
    def __init__(self, data, uid):
        self.data, self.message, self.alerts = data, _Msg(uid), []
        self.from_user = type("U", (), {"id": uid, "username": "c", "first_name": "К"})()

    async def answer(self, text="", **kw):
        if text:
            self.alerts.append(text)


class _State:
    def __init__(self, **data):
        self.data, self.state = dict(data), None

    async def set_state(self, v):
        self.state = v

    async def update_data(self, **kw):
        self.data.update(kw)

    async def get_data(self):
        return dict(self.data)

    async def clear(self):
        self.data.clear()


def _buttons(markup) -> list[str]:
    return [b.callback_data for row in markup.inline_keyboard for b in row] if markup else []


async def no_receipt(conn, bot) -> None:
    from app.handlers import deposit as dp

    await fresh(conn)
    d = await dep(conn, A, 2503)
    call = _Call("dep:paid", A)
    real_sleep = asyncio.sleep
    waits = []

    async def quick(seconds):
        waits.append(seconds)
        await real_sleep(0)

    asyncio.sleep = quick
    bot.clear()
    try:
        await dp.cb_paid(call, _State(amount=2503, deposit_id=d.id), conn, bot)
        shown = call.message.texts[-1]
        check("«Я оплатил» — чек не просим, ждём банк",
              "лозим нест" in shown and "скриншоти чекро фиристед" not in shown, shown[:160])
        check("есть «Проверить» и «Отправить чек»",
              {"dep:check", "dep:askrc"} <= set(_buttons(call.message.markups[-1])))

        c2 = _Call("dep:check", A)
        await dp.cb_check(c2, _State(amount=2503, deposit_id=d.id), conn)
        check("«Проверить» до денег — «ҳоло нарасид»", c2.alerts and "нарасид" in c2.alerts[-1], str(c2.alerts))

        await asyncio.gather(*list(dp._reminders))
        asked = [t for chat, t in bot.sent if chat == A and "чекро" in t]
        check("деньги не совпали за 5 мин → бот сам просит чек", asked and waits == [300], f"{waits} {bot.sent[-1:]}")

        # совпало — чек не просим
        d2 = await dep(conn, B, 2604)
        bot.clear()
        bank_done = asyncio.Event()

        async def after_bank(seconds):          # 5 минут проходят только после уведомления банка
            await bank_done.wait()

        asyncio.sleep = after_bank
        await dp.cb_paid(_Call("dep:paid", B), _State(amount=2604, deposit_id=d2.id), conn, bot)
        await handle(conn, bot, notice("26.04"))
        bank_done.set()
        await asyncio.gather(*list(dp._reminders))
        check("деньги совпали → зачислено, чек не просили",
              (await db.get_deposit(conn, d2.id)).status == db.DEP_APPROVED
              and not [t for chat, t in bot.sent if chat == B and "скриншоти чекро" in t])
        c3 = _Call("dep:check", B)
        await dp.cb_check(c3, _State(amount=2604, deposit_id=d2.id), conn)
        check("«Проверить» после зачисления — «пур шуд»", "пур шуд" in c3.message.texts[-1])
    finally:
        asyncio.sleep = real_sleep


# ───────────────────────────────────────────── вход юзербота


async def userbot_login(tmp: Path) -> None:
    from telethon.errors import (PhoneCodeExpiredError, PhoneCodeInvalidError,
                                 SessionPasswordNeededError)

    from app.userbot import login as lg

    class Client:
        alive_session = False

        def __init__(self, script):
            self.script, self.connected, self.hashes, self.codes_sent = list(script), False, [], 0
            self.password = None

        async def connect(self):
            self.connected = True

        def is_connected(self):
            return self.connected

        async def is_user_authorized(self):
            return self.alive_session

        async def disconnect(self):
            self.connected = False

        async def send_code_request(self, phone):
            self.codes_sent += 1
            return type("S", (), {"phone_code_hash": f"hash{self.codes_sent}"})()

        async def sign_in(self, phone=None, code=None, phone_code_hash=None, password=None):
            assert self.connected, "sign_in без соединения"
            if password is not None:
                self.password = password
                return True
            self.hashes.append(phone_code_hash)
            step = self.script.pop(0)
            if step == "drop":                       # неверный код, и связь оборвалась
                self.connected = False
                raise PhoneCodeInvalidError(request=None)
            if step:
                raise step(request=None)
            return True

    def run(client, answers, secret=("pw",), session=None):
        said = []
        it, sec = iter(answers), iter(secret)
        return lg.login(lambda: client, session or tmp / "none.session",
                        lambda _: next(it), lambda _: next(sec), said.append), said

    c = Client(["drop", None])
    coro, said = run(c, ["+992 90-123-45-67", "11111", "22222"])
    got = await coro
    check("неверный код + обрыв связи + верный код → вход прошёл", got is c, str(said))
    check("хэш кода тот же", c.hashes == ["hash1", "hash1"], str(c.hashes))
    check("номер очищен от пробелов и дефисов", c.codes_sent == 1)

    c = Client([PhoneCodeExpiredError, None])
    coro, said = run(c, ["+992901234567", "11111", "33333"])
    await coro
    check("устаревший код → новый запрошен", c.codes_sent == 2 and c.hashes == ["hash1", "hash2"], str(c.hashes))

    c = Client([SessionPasswordNeededError])
    coro, said = run(c, ["+992901234567", "11111"], secret=("секрет",))
    await coro
    check("облачный пароль → спрошен", c.password == "секрет")

    c = Client([PhoneCodeInvalidError] * 3)
    coro, said = run(c, ["+992901234567", "1", "2", "3"])
    try:
        await coro
        check("три неверных кода → понятный отказ", False)
    except lg.LoginFailed as exc:
        check("три неверных кода → понятный отказ", "три раза" in str(exc), str(exc))

    dead = tmp / "userbot.session"
    dead.write_text("старый сеанс")
    c = Client([None])
    coro, said = run(c, ["+992901234567", "11111"], session=dead)
    await coro
    check("мёртвый файл сеанса → переименован в .old",
          not dead.exists() and (tmp / "userbot.session.old").read_text() == "старый сеанс", str(said))


async def main() -> None:
    import tempfile

    for sfx in ("", "-wal", "-shm"):
        Path(str(settings.db_file) + sfx).unlink(missing_ok=True)
    conn = await db.connect()
    bot = FakeBot()
    try:
        await db.init(conn)
        await runtime.load(conn)
        await db.upsert_user(conn, A, "a", "Клиент А")
        await db.upsert_user(conn, B, "b", "Клиент Б")
        parsing()
        await kopecks(conn)
        await matching(conn, bot)
        await no_receipt(conn, bot)
    finally:
        await conn.close()
    await foreign_message()
    with tempfile.TemporaryDirectory() as tmp:
        await userbot_login(Path(tmp))

    print(f"\n{'=' * 52}\nПройдено: {len(PASS)}   Провалено: {len(FAIL)}")
    if FAIL:
        print("ПРОВАЛЫ:", ", ".join(FAIL))
    sys.exit(1 if FAIL else 0)


asyncio.run(main())
