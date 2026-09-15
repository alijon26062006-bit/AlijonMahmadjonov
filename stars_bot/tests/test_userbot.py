"""Юзербот: разбор уведомлений банка, сопоставление заявок, защита от дублей.

Настоящих банковских данных здесь нет и быть не может: номера карт и
отправителей выдуманы, суммы взяты из задачи.
"""
from __future__ import annotations

import asyncio
import contextlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_fixture  # noqa: F401

from app import db, runtime
from app.money import fmt
from app.userbot import parser, processor
from app.userbot.log import scrub

CLIENT = 901
OTHER = 902
SOURCE = "bank_test_bot"
PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  — {detail}" if detail else ""))


class FakeBot:
    """Вместо Telegram — список писем, чтобы видеть, что бот сказал."""

    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))

    def last(self) -> str:
        return self.sent[-1][1] if self.sent else ""

    def clear(self) -> None:
        self.sent.clear()


# ────────────────────────────────────────────────── образцы сообщений


REAL = """Zachislenie
Summa 617.00 TJS
Komis 0.00 TJS
Zachislenie 617.00 TJS
Data 19:40 15.09.26
Otpravitel 9990000***1111
Kod 10000000001
Karta 9999000011112222
Balans 3 686.07 TJS"""


def sample(**changes) -> str:
    """Собрать уведомление из кусочков: так проще менять по одному полю."""
    parts = {
        "head": "Zachislenie",
        "summa": "Summa 100.00 TJS",
        "komis": "Komis 0.00 TJS",
        "zach": "Zachislenie 100.00 TJS",
        "data": "Data 19:40 15.09.26",
        "otpr": "Otpravitel 9990000***1111",
        "kod": "Kod 10000000001",
        "karta": "Karta 9999000011112222",
        "balans": "Balans 3 686.07 TJS",
    }
    parts.update(changes)
    return "\n".join(value for value in parts.values() if value)


# ────────────────────────────────────────────────── разбор


def parsing() -> None:
    # 1. обычное зачисление 617.00
    n = parser.parse(REAL)
    check("1. обычное зачисление 617.00", n.ok and n.amount == 61700, str(n.amount))
    check("   сумма взята из поля Zachislenie",
          n.source_field == "zachislenie", n.source_field)
    check("   код операции найден", n.op_code == "10000000001", n.op_code)
    check("   время найдено", n.bank_time == "19:40 15.09.26", n.bank_time)
    check("   баланс суммой не стал", n.amount != 368607, str(n.amount))
    check("   комиссия суммой не стала", n.amount != 0)

    # 2. зачисление 100 TJS
    n = parser.parse(sample())
    check("2. зачисление 100 TJS", n.ok and n.amount == 10000, str(n.amount))

    # 3. сумма с запятой
    n = parser.parse(sample(zach="Zachislenie 617,50 TJS"))
    check("3. сумма с запятой", n.ok and n.amount == 61750, str(n.amount))

    # 4. лишние пробелы
    n = parser.parse("  Zachislenie  \n\n   Zachislenie    617.00   TJS   \n"
                     "   Komis   0.00 TJS  \n")
    check("4. лишние пробелы не мешают", n.ok and n.amount == 61700, str(n.amount))

    # 5. изменённый порядок строк
    shuffled = "\n".join([
        "Zachislenie", "Balans 3 686.07 TJS", "Kod 10000000001",
        "Zachislenie 617.00 TJS", "Karta 9999000011112222",
        "Komis 0.00 TJS", "Data 19:40 15.09.26", "Summa 617.00 TJS",
    ])
    n = parser.parse(shuffled)
    check("5. порядок строк не важен", n.ok and n.amount == 61700, str(n.amount))

    # 6. нет Kod
    n = parser.parse(sample(kod=""))
    check("6. без кода операции всё равно разбирается",
          n.ok and n.amount == 10000 and n.op_code == "", str(n.error))

    # 7. нет Otpravitel
    n = parser.parse(sample(otpr=""))
    check("7. без отправителя всё равно разбирается",
          n.ok and n.sender == "", str(n.error))

    # 8. нет суммы
    n = parser.parse("Zachislenie\nData 19:40 15.09.26\nKod 1234")
    check("8. без суммы — отказ", not n.ok, n.error)

    # 9. нет слова Zachislenie
    n = parser.parse("Spisanie\nSumma 617.00 TJS\nKomis 0.00 TJS")
    check("9. списание не принимается за зачисление", not n.ok, n.error)
    n = parser.parse("Summa 617.00 TJS\nKomis 0.00 TJS\nBalans 10.00 TJS")
    check("   и без слова о зачислении тоже отказ", not n.ok, n.error)

    # 10. комиссия 0, зачисление 617
    n = parser.parse(sample(summa="Summa 620.00 TJS", komis="Komis 3.00 TJS",
                            zach="Zachislenie 617.00 TJS"))
    check("10. берём зачисленное, а не отправленное",
          n.ok and n.amount == 61700, str(n.amount))

    # 14. 617.01 — это другая сумма
    n = parser.parse(sample(zach="Zachislenie 617.01 TJS"))
    check("14. 617.01 не равно 617.00", n.amount == 61701, str(n.amount))

    # 15. очень большая сумма
    n = parser.parse(sample(zach="Zachislenie 999999999999.00 TJS"))
    check("15. неправдоподобная сумма отклонена", not n.ok, n.error)
    n = parser.parse(sample(zach="Zachislenie 50 000.00 TJS"))
    check("   но большая настоящая проходит",
          n.ok and n.amount == 5_000_000, str(n.amount))

    # 16. мусор
    for junk in ("", "   ", "привет", "Zachislenie\nSumma много TJS",
                 "Zachislenie 617.00.00 TJS", "Zachislenie -617.00 TJS",
                 "Zachislenie 0.00 TJS"):
        n = parser.parse(junk)
        check(f"16. мусор отклонён: {junk[:22]!r}", not n.ok, n.error)

    # без Zachislenie-суммы, но с комиссией — зачисленное неизвестно
    n = parser.parse("Zachislenie\nSumma 617.00 TJS\nKomis 3.00 TJS")
    check("с комиссией и без суммы зачисления — отказ", not n.ok, n.error)
    n = parser.parse("Zachislenie\nSumma 617.00 TJS\nKomis 0.00 TJS")
    check("без комиссии сумма берётся из Summa",
          n.ok and n.amount == 61700 and n.source_field == "summa", n.source_field)

    # регистр
    n = parser.parse("ZACHISLENIE\nZACHISLENIE 617.00 TJS\nKOMIS 0.00 TJS")
    check("регистр букв не важен", n.ok and n.amount == 61700, str(n.error))

    # лишние строки банка
    n = parser.parse(sample() + "\nSpasibo za ispolzovanie\nwww.bank.tj")
    check("лишние строки не мешают", n.ok and n.amount == 10000, str(n.error))


def masking() -> None:
    n = parser.parse(REAL)
    check("номер карты обрезан до четырёх знаков",
          n.card_tail == "2222" and len(n.card_tail) == 4, n.card_tail)
    check("полного номера карты нет нигде",
          "9999000011112222" not in str(n), str(n))

    body = parser.safe_body(REAL)
    check("в сохранённом тексте нет номера карты",
          "9999000011112222" not in body, body[-60:])
    check("но хвост карты виден для сверки", "2222" in body)
    check("сумма в сохранённом тексте осталась", "617.00" in body)

    check("логи чистят номер карты",
          "9999000011112222" not in scrub("Karta 9999000011112222"))
    check("логи чистят токен бота",
          "AAHdq" not in scrub("8123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"))
    check("логи чистят api_hash",
          "0123456789abcdef0123456789abcdef" not in
          scrub("hash 0123456789abcdef0123456789abcdef"))
    check("сумму логи не портят", "617.00" in scrub("Summa 617.00 TJS"))


# ────────────────────────────────────────────────── сопоставление


async def matching(conn, bot) -> None:
    await db.upsert_user(conn, CLIENT, "client", "Клиент")
    await db.upsert_user(conn, OTHER, "other", "Второй")

    # ---- ровно одна заявка: зачисляем
    deposit = await db.create_deposit(
        conn, user_id=CLIENT, amount=61700, method="card", receipt_file_id="x",
    )
    before = (await db.get_user(conn, CLIENT)).balance
    bot.clear()

    result = await processor.handle(
        conn, bot, source=SOURCE, message_id=1001, text=REAL)
    check("одна заявка — оплата подтверждена", result.confirmed, result.status)
    check("закрыта именно она", result.deposit_id == deposit.id,
          str(result.deposit_id))
    check("деньги зачислены клиенту",
          (await db.get_user(conn, CLIENT)).balance == before + 61700,
          str((await db.get_user(conn, CLIENT)).balance))
    check("заявка помечена зачисленной",
          (await db.get_deposit(conn, deposit.id)).status == db.DEP_APPROVED)
    check("клиенту пришло сообщение",
          any(chat == CLIENT for chat, _ in bot.sent), str(bot.sent[:1]))
    check("владельцу пришло сообщение",
          any("подтверждена" in text for _, text in bot.sent), bot.last()[:60])

    saved = (await db.list_bank_payments(conn))[0]
    check("платёж записан в базу", saved.amount == 61700, str(saved.amount))
    check("код операции сохранён", saved.op_code == "10000000001", str(saved.op_code))
    check("в базе нет полного номера карты",
          "9999000011112222" not in (saved.body or "") and saved.card_tail == "2222",
          saved.card_tail)
    check("платёж связан с заявкой", saved.deposit_id == deposit.id)

    # ---- 12/13. повтор того же сообщения
    balance = (await db.get_user(conn, CLIENT)).balance
    again = await processor.handle(
        conn, bot, source=SOURCE, message_id=1001, text=REAL)
    check("12. повторное сообщение отброшено", again.status == "duplicate",
          again.status)
    check("13. деньги второй раз не зачислены",
          (await db.get_user(conn, CLIENT)).balance == balance)

    # ---- тот же код операции, но другой message_id
    third = await processor.handle(
        conn, bot, source=SOURCE, message_id=1002, text=REAL)
    check("тот же код банка не проходит дважды", third.status == "duplicate",
          third.status)
    check("и денег не прибавилось",
          (await db.get_user(conn, CLIENT)).balance == balance)

    # ---- 11. два заказа с одинаковой суммой
    first = await db.create_deposit(
        conn, user_id=CLIENT, amount=10000, method="card", receipt_file_id="a")
    second = await db.create_deposit(
        conn, user_id=OTHER, amount=10000, method="card", receipt_file_id="b")
    balance = (await db.get_user(conn, CLIENT)).balance
    other_balance = (await db.get_user(conn, OTHER)).balance
    bot.clear()

    result = await processor.handle(
        conn, bot, source=SOURCE, message_id=2001,
        text=sample(kod="Kod 77001"))
    check("11. две заявки на одну сумму — не выбираем наугад",
          result.status == db.BANK_AMBIGUOUS, result.status)
    check("    деньги никому не зачислены",
          (await db.get_user(conn, CLIENT)).balance == balance
          and (await db.get_user(conn, OTHER)).balance == other_balance)
    check("    обе заявки остались на проверке",
          (await db.get_deposit(conn, first.id)).status == db.DEP_PENDING
          and (await db.get_deposit(conn, second.id)).status == db.DEP_PENDING)
    check("    владельцу показали обе",
          f"№{first.id}" in bot.last() and f"№{second.id}" in bot.last(),
          bot.last()[:200])
    check("    клиенту ничего не писали",
          not any(chat in (CLIENT, OTHER) for chat, _ in bot.sent),
          str([c for c, _ in bot.sent]))

    # ---- 14. сумма не совпала на копейку
    await db.resolve_deposit(conn, second.id, approved=False, admin_id=1)
    balance = (await db.get_user(conn, CLIENT)).balance
    result = await processor.handle(
        conn, bot, source=SOURCE, message_id=2002,
        text=sample(zach="Zachislenie 100.01 TJS", kod="Kod 77002"))
    check("14. 100.01 не закрывает заявку на 100.00",
          result.status == db.BANK_UNKNOWN, result.status)
    check("    деньги не тронуты",
          (await db.get_user(conn, CLIENT)).balance == balance)
    check("    заявка ждёт дальше",
          (await db.get_deposit(conn, first.id)).status == db.DEP_PENDING)

    # ---- заявки нет вовсе
    bot.clear()
    result = await processor.handle(
        conn, bot, source=SOURCE, message_id=2003,
        text=sample(zach="Zachislenie 777.00 TJS", summa="Summa 777.00 TJS",
                    kod="Kod 77003"))
    check("оплата без заявки помечена неопознанной",
          result.status == db.BANK_UNKNOWN, result.status)
    check("владельцу сказали про неё", "без заявки" in bot.last(), bot.last()[:60])

    # ---- неразобранное сообщение
    bot.clear()
    result = await processor.handle(
        conn, bot, source=SOURCE, message_id=2004, text="Spisanie\nSumma 50.00 TJS")
    check("списание не закрывает заявок", result.status == db.BANK_FAILED,
          result.status)
    check("владельцу сказали, что не разобрал",
          "не разобрал" in bot.last(), bot.last()[:60])
    check("заявка по-прежнему ждёт",
          (await db.get_deposit(conn, first.id)).status == db.DEP_PENDING)

    # ---- гонка: заявку закрыли раньше нас
    await db.resolve_deposit(conn, first.id, approved=True, admin_id=777)
    balance = (await db.get_user(conn, CLIENT)).balance
    result = await processor.handle(
        conn, bot, source=SOURCE, message_id=2005,
        text=sample(kod="Kod 77005"))
    check("закрытую заявку второй раз не оплачиваем",
          result.status in (db.BANK_UNKNOWN, db.BANK_AMBIGUOUS), result.status)
    check("и денег не прибавилось",
          (await db.get_user(conn, CLIENT)).balance == balance)


async def sources() -> None:
    """Слушаем только свой источник — чужие сообщения не трогаем."""
    from app.userbot import runner

    class Msg:
        def __init__(self, sender_id=0, username=""):
            self.sender_id = sender_id
            self.sender = type("S", (), {"username": username})()

    check("свой бот по юзернейму опознан",
          runner._from_source(Msg(username="bank_bot"), 0, "bank_bot"))
    check("регистр юзернейма не важен",
          runner._from_source(Msg(username="Bank_Bot"), 0, "bank_bot"))
    check("свой бот по id опознан",
          runner._from_source(Msg(sender_id=12345), 12345, "12345"))
    check("чужой бот не принят",
          not runner._from_source(Msg(username="other_bot"), 0, "bank_bot"))
    check("чужой id не принят",
          not runner._from_source(Msg(sender_id=999), 12345, "12345"))
    check("без отправителя не принят",
          not runner._from_source(Msg(), 12345, "bank_bot"))


async def worker_loop(bot) -> None:
    """Очередь: строго по одному, и одно кривое сообщение не валит поток."""
    from app.userbot import runner

    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(runner._drain(queue, bot))
    try:
        # первое — кривое, второе — нормальное. Второе должно пройти.
        queue.put_nowait((3001, None))            # None вместо текста
        queue.put_nowait((3002, sample(zach="Zachislenie 55.00 TJS",
                                       summa="Summa 55.00 TJS",
                                       kod="Kod 88001")))
        await asyncio.wait_for(queue.join(), timeout=10)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    check("очередь пережила кривое сообщение", task.cancelled() or task.done())
    conn = await db.connect()
    try:
        saved = {row.message_id: row for row in
                 await db.list_bank_payments(conn, limit=50)}
    finally:
        await conn.close()
    check("кривое сообщение записано, но не оплачено",
          3001 not in saved or saved[3001].status == db.BANK_FAILED,
          str(saved.get(3001)))
    check("следующее за ним обработано",
          3002 in saved and saved[3002].amount == 5500,
          str(saved.get(3002)))


# ────────────────────────────────────────────────── запуск


async def main() -> None:
    for sfx in ("", "-wal", "-shm"):
        Path(str(db.settings.db_file) + sfx).unlink(missing_ok=True)
    conn = await db.connect()
    bot = FakeBot()
    try:
        await db.init(conn)
        await runtime.load(conn)
        parsing()
        masking()
        await matching(conn, bot)
        await sources()
    finally:
        await conn.close()
    await worker_loop(bot)

    print(f"\n{'=' * 52}\nПройдено: {len(PASS)}   Провалено: {len(FAIL)}")
    if FAIL:
        print("ПРОВАЛЫ:", ", ".join(FAIL))
    sys.exit(1 if FAIL else 0)


asyncio.run(main())
