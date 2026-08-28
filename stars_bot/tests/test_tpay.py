"""TelegaPAY: разбор ответов шлюза, пересчёт валюты, зачисление, панель."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_fixture  # noqa: F401

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Chat, Message, User
from pydantic import PrivateAttr

from app import db, keyboards, runtime
from app.handlers import deposit as dep_h
from app.handlers import panel
from app.services import telegapay, tpay
from app.services.telegapay import PaymentError, TelegaPay

BUYER = 777
PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  — {detail}" if detail else ""))


# ───────────────────────────── подменяем сеть, разбор оставляем настоящим


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status = payload, status

    async def json(self, content_type=None):
        return self.payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    """Отвечает по пути запроса и запоминает, с какими заголовками звали."""

    def __init__(self, replies: dict, need_header: str | None = "API-KEY"):
        self.replies, self.need_header = replies, need_header
        self.calls: list[tuple[str, dict, dict]] = []

    def post(self, url, json=None, headers=None):
        path = url.rsplit("/api/v1", 1)[-1]
        self.calls.append((path, json or {}, headers or {}))
        if self.need_header and self.need_header not in (headers or {}):
            return FakeResponse({"error": "unauthorized"}, status=401)
        reply = self.replies.get(path)
        if reply is None:
            return FakeResponse({"error": "not found"}, status=404)
        return FakeResponse(reply)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def with_session(session):
    telegapay.aiohttp.ClientSession = lambda *a, **kw: session


REAL_SESSION = telegapay.aiohttp.ClientSession


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))


class SpyMessage(Message):
    _log: list = PrivateAttr(default_factory=list)

    async def answer(self, text, reply_markup=None, **kw):
        self._log.append((text, reply_markup))
        return self

    async def edit_text(self, text, reply_markup=None, **kw):
        self._log.append((text, reply_markup))
        return self

    @property
    def last(self) -> str:
        return self._log[-1][0] if self._log else ""

    @property
    def markup(self):
        return self._log[-1][1] if self._log else None


class SpyCallback(CallbackQuery):
    _alerts: list = PrivateAttr(default_factory=list)

    async def answer(self, text="", **kw):
        if text:
            self._alerts.append(text)

    @property
    def last(self) -> str:
        return self.message.last

    @property
    def alerts(self) -> list:
        return self._alerts


def msg(text=None, uid=BUYER) -> SpyMessage:
    user = User(id=uid, is_bot=False, first_name="Клиент", username="buyer")
    return SpyMessage.model_construct(
        message_id=1, date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        chat=Chat(id=uid, type="private"), from_user=user, text=text,
    )


def call_of(data: str, uid=BUYER) -> SpyCallback:
    user = User(id=uid, is_bot=False, first_name="Клиент", username="buyer")
    return SpyCallback.model_construct(
        id="1", from_user=user, chat_instance="x", data=data, message=msg(uid=uid),
    )


def buttons(markup) -> list[str]:
    return [b.text for row in markup.inline_keyboard for b in row]


PAYLINK = {"/create_paylink": {"payment_url": "https://pay.example/abc",
                               "transaction_id": "tx-1"}}


# ─────────────────────────────────────────────────────────── клиент шлюза


async def client_tests() -> None:
    session = FakeSession({"/get_methods": {"methods": ["sbp", "card"]}})
    with_session(session)
    api = TelegaPay("kluch")
    body = await api.get_methods("RUB")
    check("метод оплаты запрашивается", body["methods"] == ["sbp", "card"])
    check("ключ ушёл в заголовке", session.calls[-1][2].get("API-KEY") == "kluch")

    # шлюз хочет другой заголовок — подбираем сами
    session = FakeSession({"/get_methods": {"ok": True}}, need_header="Authorization")
    with_session(session)
    api = TelegaPay("kluch")
    await api.get_methods()
    check("другой заголовок авторизации подбирается",
          session.calls[-1][2].get("Authorization") == "Bearer kluch",
          str(session.calls[-1][2]))
    used = len(session.calls)
    await api.get_methods()
    check("рабочий заголовок запоминается",
          len(session.calls) == used + 1, str(len(session.calls)))

    session = FakeSession({"/get_methods": {"ok": True}}, need_header="НЕТ-ТАКОГО")
    with_session(session)
    try:
        await TelegaPay("kluch").get_methods()
        check("неверный ключ — ошибка", False)
    except PaymentError as exc:
        check("неверный ключ — ошибка", "не принят" in str(exc), str(exc))

    try:
        await TelegaPay("").get_methods()
        check("пустой ключ — ошибка", False)
    except PaymentError:
        check("пустой ключ — ошибка", True)

    # ссылка на оплату в разных обёртках
    for payload, where in (
        ({"payment_url": "https://p/1", "transaction_id": "t1"}, "в корне"),
        ({"data": {"pay_url": "https://p/1", "id": "t1"}}, "в data"),
        ({"result": {"link": "https://p/1", "uuid": "t1"}}, "в result"),
    ):
        with_session(FakeSession({"/create_paylink": payload}))
        link = await TelegaPay("k").create_paylink(
            amount=Decimal("500"), currency="RUB", order_id="dep1")
        check(f"ссылка найдена {where}", link.url == "https://p/1", link.url)
        check(f"номер транзакции найден {where}", link.transaction_id == "t1")

    with_session(FakeSession({"/create_paylink": {"ok": True}}))
    try:
        await TelegaPay("k").create_paylink(
            amount=Decimal("1"), currency="RUB", order_id="x")
        check("ответ без ссылки — ошибка", False)
    except PaymentError as exc:
        check("ответ без ссылки — ошибка", "нет ссылки" in str(exc), str(exc))

    # статусы
    for raw, paid, failed in (
        ("paid", True, False), ("SUCCESS", True, False), ("completed", True, False),
        ("pending", False, False), ("processing", False, False),
        ("expired", False, True), ("cancelled", False, True),
        ("что-то новое", False, False),
    ):
        with_session(FakeSession({"/check_status": {"status": raw}}))
        status = await TelegaPay("k").check_status("t1")
        check(f"статус «{raw}» разобран верно",
              status.paid is paid and status.failed is failed,
              f"paid={status.paid} failed={status.failed}")

    with_session(FakeSession({"/check_status": {"data": {"state": "paid",
                                                         "real_amount": "500.03"}}}))
    status = await TelegaPay("k").check_status("t1")
    check("подменённая сумма читается", status.amount == Decimal("500.03"),
          str(status.amount))


# ──────────────────────────────────────────────────────── пересчёт валюты


async def money(conn) -> None:
    await runtime.set_value(conn, "tpay_currency", "RUB")
    await runtime.set_value(conn, "tpay_rate_diram", "12")   # 1 ₽ = 0.12 с.

    check("сомони переводятся в рубли", tpay.to_currency(60_00) == Decimal("500"),
          str(tpay.to_currency(60_00)))
    check("обратный пересчёт сходится", tpay.to_diram(Decimal("500")) == 60_00)
    check("копейки округляются", tpay.to_currency(1000) == Decimal("83.33"),
          str(tpay.to_currency(1000)))

    await runtime.set_value(conn, "tpay_rate_diram", "0")
    check("без курса пересчёта нет", tpay.to_currency(60_00) is None)
    check("без курса способ выключен", tpay.enabled() is False)
    await runtime.set_value(conn, "tpay_rate_diram", "12")


# ──────────────────────────────────────────────────────── путь пополнения


async def flow(conn) -> None:
    storage = MemoryStorage()
    state = FSMContext(storage=storage,
                       key=StorageKey(bot_id=1, chat_id=BUYER, user_id=BUYER))
    bot = FakeBot()
    await db.upsert_user(conn, BUYER, "buyer", "Клиент")
    await runtime.set_value(conn, "tpay_key", "kluch")
    await runtime.set_value(conn, "tpay_on", "1")

    check("способ включён", tpay.enabled() is True)
    check("кнопка появилась в меню пополнения",
          any("Карта РФ" in b for b in buttons(keyboards.deposit_methods())),
          str(buttons(keyboards.deposit_methods())))

    call = call_of("dep:tpay")
    await dep_h.cb_tpay(call, state)
    check("бот просит сумму в сомони", "в сомони" in call.last, call.last[:100])
    check("показан курс", "1 RUB = 0.12" in call.last, call.last[:120])
    check("ждём сумму", await state.get_state() == "Deposit:tpay_amount")

    small = msg("1")
    await dep_h.on_tpay_amount(small, state, conn, bot)
    check("сумма меньше минимума отклонена", "Минимальная" in small.last)

    with_session(FakeSession(PAYLINK))
    message = msg("60")
    await dep_h.on_tpay_amount(message, state, conn, bot)
    check("счёт выставлен", "Счёт на оплату" in message.last, message.last[:60])
    check("видно, сколько зачислится", "60.00 с." in message.last)
    check("видно, сколько платить", "500.00 RUB" in message.last, message.last)
    check("есть кнопка оплаты", "💳 Оплатить" in buttons(message.markup))
    check("есть кнопка проверки",
          any("проверить" in b for b in buttons(message.markup)))
    check("шаг закрыт", await state.get_state() is None)

    deposits = await db.list_deposits(conn, user_id=BUYER)
    dep = deposits[0]
    check("заявка создана", dep.amount == 60_00 and dep.method == "telegapay")
    check("заявка ждёт оплаты", dep.status == db.DEP_PENDING)
    check("номер транзакции сохранён", dep.reference == "tx-1", str(dep.reference))

    # ---------------------------------------------- ещё не оплачено
    with_session(FakeSession({"/check_status": {"status": "pending"}}))
    call = call_of(f"dep:tcheck:{dep.id}")
    await dep_h.cb_tpay_check(call, conn, bot)
    check("непрошедший платёж не зачисляется",
          (await db.get_user(conn, BUYER)).balance == 0)
    check("клиенту сказано подождать", "не найдена" in call.last, call.last[:80])

    # ---------------------------------------------- незнакомый статус
    with_session(FakeSession({"/check_status": {"status": "какой-то_новый"}}))
    await dep_h.cb_tpay_check(call_of(f"dep:tcheck:{dep.id}"), conn, bot)
    check("незнакомый статус не считается оплатой",
          (await db.get_user(conn, BUYER)).balance == 0)

    # ---------------------------------------------- оплачено
    with_session(FakeSession({"/check_status": {"status": "paid"}}))
    await dep_h.cb_tpay_check(call_of(f"dep:tcheck:{dep.id}"), conn, bot)
    check("после оплаты баланс пополнен",
          (await db.get_user(conn, BUYER)).balance == 60_00,
          str((await db.get_user(conn, BUYER)).balance))
    check("заявка закрыта",
          (await db.get_deposit(conn, dep.id)).status == db.DEP_APPROVED)
    check("клиенту пришло сообщение о зачислении",
          any("пополнен" in t for _, t in bot.sent), str(bot.sent))
    check("пополнение попало в total_deposit",
          (await db.get_user(conn, BUYER)).total_deposit == 60_00)

    # ---------------------------------------------- второй раз не зачислится
    before = (await db.get_user(conn, BUYER)).balance
    await dep_h.cb_tpay_check(call_of(f"dep:tcheck:{dep.id}"), conn, bot)
    check("повторная проверка не удваивает баланс",
          (await db.get_user(conn, BUYER)).balance == before)

    # ---------------------------------------------- платёж не создался
    with_session(FakeSession({}))
    await state.set_state(dep_h.Deposit.tpay_amount)
    message = msg("60")
    await dep_h.on_tpay_amount(message, state, conn, bot)
    check("отказ шлюза объяснён клиенту", "не создался" in message.last,
          message.last[:80])
    stuck = [d for d in await db.list_deposits(conn, user_id=BUYER)
             if d.status == db.DEP_PENDING]
    check("висящей заявки не осталось", stuck == [], str(stuck))

    # ---------------------------------------------- отменённый платёж
    with_session(FakeSession(PAYLINK))
    await state.set_state(dep_h.Deposit.tpay_amount)
    await dep_h.on_tpay_amount(msg("60"), state, conn, bot)
    fresh = [d for d in await db.list_deposits(conn, user_id=BUYER)
             if d.status == db.DEP_PENDING][0]
    with_session(FakeSession({"/check_status": {"status": "expired"}}))
    call = call_of(f"dep:tcheck:{fresh.id}")
    await dep_h.cb_tpay_check(call, conn, bot)
    check("отменённый платёж закрывает заявку",
          (await db.get_deposit(conn, fresh.id)).status == db.DEP_REJECTED)
    check("баланс при отмене не растёт",
          (await db.get_user(conn, BUYER)).balance == before)
    check("клиенту сказано, что платёж не прошёл", "не прошёл" in call.last)

    # ---------------------------------------------- чужая заявка
    await db.upsert_user(conn, 999, "chuzhoi", "Чужой")
    call = call_of(f"dep:tcheck:{dep.id}", uid=999)
    await dep_h.cb_tpay_check(call, conn, bot)
    check("чужую заявку проверить нельзя",
          any("не найдена" in a for a in call.alerts), str(call.alerts))


# ────────────────────────────────────────────────────────────── панель


async def panel_screens(conn) -> None:
    call = call_of("pn:tpay")
    await panel.cb_tpay(call, FSMContext(storage=MemoryStorage(),
                                         key=StorageKey(bot_id=1, chat_id=111, user_id=111)))
    check("раздел открывается", "TelegaPAY" in call.last)
    check("ключ показан обрезанным", "kluch" not in call.last, call.last[:200])
    check("виден курс", "1 RUB = 0.12" in call.last, call.last[:200])

    with_session(FakeSession({"/get_methods": {"methods": ["sbp"]}}))
    call = call_of("pn:tpay_check")
    await panel.cb_tpay_check(call)
    check("проверка связи проходит", "Способы оплаты: ✅" in call.last, call.last[:300])
    check("показан рабочий заголовок", "API-KEY" in call.last)
    check("показан сырой ответ", "sbp" in call.last)

    with_session(FakeSession({}, need_header="НЕТ"))
    call = call_of("pn:tpay_check")
    await panel.cb_tpay_check(call)
    check("отказ показан честно", "❌" in call.last, call.last[:200])
    check("подсказано про одобрение магазина",
          "TelegaPaySalesBot" in call.last, call.last[-200:])

    await runtime.set_value(conn, "tpay_on", "0")
    await runtime.set_value(conn, "tpay_rate_diram", "0")
    call = call_of("pn:tpay_toggle")
    await panel.cb_tpay_toggle(call, conn)
    check("без курса способ не включить", runtime.get_bool("tpay_on") is False)
    check("и сказано почему", any("курс" in a for a in call.alerts), str(call.alerts))

    await runtime.set_value(conn, "tpay_rate_diram", "12")
    await panel.cb_tpay_toggle(call_of("pn:tpay_toggle"), conn)
    check("с курсом включается", runtime.get_bool("tpay_on") is True)

    check("раздел есть в главном меню панели",
          any("TelegaPAY" in b.text
              for r in panel.home_kb().inline_keyboard for b in r))


async def main() -> None:
    await client_tests()
    for sfx in ("", "-wal", "-shm"):
        Path(str(db.settings.db_file) + sfx).unlink(missing_ok=True)
    conn = await db.connect()
    try:
        await db.init(conn)
        await runtime.load(conn)
        await money(conn)
        await flow(conn)
        await panel_screens(conn)
    finally:
        telegapay.aiohttp.ClientSession = REAL_SESSION
        await conn.close()
    print(f"\n{'=' * 52}\nПройдено: {len(PASS)}   Провалено: {len(FAIL)}")
    if FAIL:
        print("ПРОВАЛЫ:", ", ".join(FAIL))
    sys.exit(1 if FAIL else 0)


asyncio.run(main())
