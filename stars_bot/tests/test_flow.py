"""Сквозной прогон пользовательского сценария через настоящие обработчики.

Telegram подменён заглушками, всё остальное — боевой код: FSM, база,
списание баланса, выдача.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_fixture  # noqa: F401  — фиксирует настройки до импорта app

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from app import db, runtime
from app.handlers import deposit as dep_h
from app.handlers import menu as menu_h
from app.handlers import profile as prof_h
from app.handlers import shop as shop_h
from app.handlers import support as sup_h
from app.money import fmt
from app.services.fragment import DeliveryProvider, DeliveryResult, Recipient

USER_ID = 777
PASS, FAIL = [], []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"{'✅' if condition else '❌'} {name}" + (f"  — {detail}" if detail else ""))


class FakeUser:
    def __init__(self, user_id=USER_ID, username="buyer", first_name="Покупатель"):
        self.id, self.username, self.first_name = user_id, username, first_name


class FakeBot:
    def __init__(self):
        self.messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append((chat_id, text))

    async def me(self):
        return FakeUser(1, "test_bot", "Bot")


class FakePhoto:
    file_id = "photo-123"


class FakeMessage:
    """Сообщение от пользователя. Ответы бота копятся в .replies."""

    def __init__(self, text=None, user=None, photo=False, bot=None):
        self.text = text
        self.from_user = user or FakeUser()
        self.photo = [FakePhoto()] if photo else None
        self.document = None
        self.bot = bot or FakeBot()
        self.replies: list[str] = []
        self.copies: list[int] = []

    async def answer(self, text, **kwargs):
        self.replies.append(text)
        return self

    async def edit_text(self, text, **kwargs):
        self.replies.append(text)
        return self

    async def edit_reply_markup(self, **kwargs):
        return self

    async def reply(self, text, **kwargs):
        self.replies.append(text)
        return self

    async def copy_to(self, chat_id, **kwargs):
        self.copies.append(chat_id)

    @property
    def last(self) -> str:
        return self.replies[-1] if self.replies else ""


class FakeCallback:
    def __init__(self, data, user=None, bot=None):
        self.data = data
        self.from_user = user or FakeUser()
        self.bot = bot or FakeBot()
        self.message = FakeMessage(user=self.from_user, bot=self.bot)
        self.alerts: list[str] = []

    async def answer(self, text="", **kwargs):
        if text:
            self.alerts.append(text)

    @property
    def last(self) -> str:
        return self.message.last


class OkProvider(DeliveryProvider):
    def __init__(self):
        self.delivered: list[tuple[str, int]] = []

    async def deliver_stars(self, username, amount):
        self.delivered.append((username, amount))
        return DeliveryResult(order_id="frg-1", raw={})

    async def deliver_premium(self, username, months):
        self.delivered.append((username, months))
        return DeliveryResult(order_id="frg-2", raw={})

    async def resolve_recipient(self, username):
        if username == "notfound":
            return None
        return Recipient(username=username, name=f"{username.capitalize()} Test")


def make_state(storage: MemoryStorage, bot) -> FSMContext:
    return FSMContext(
        storage=storage,
        key=StorageKey(bot_id=1, chat_id=USER_ID, user_id=USER_ID),
    )


async def main() -> None:
    for suffix in ("", "-wal", "-shm"):
        Path(str(db.settings.db_file) + suffix).unlink(missing_ok=True)

    conn = await db.connect()
    try:
        await db.init(conn)
        await runtime.load(conn)
        await run_scenario(conn)
    finally:
        await conn.close()

    print(f"\n{'=' * 52}\nПройдено: {len(PASS)}   Провалено: {len(FAIL)}")
    if FAIL:
        print("ПРОВАЛЫ:", ", ".join(FAIL))
    sys.exit(1 if FAIL else 0)


async def run_scenario(conn) -> None:
    bot = FakeBot()
    storage = MemoryStorage()
    state = make_state(storage, bot)
    provider = OkProvider()

    await db.upsert_user(conn, USER_ID, "buyer", "Покупатель")

    # ---------------------------------------------------------------- /start
    msg = FakeMessage("/start", bot=bot)
    await menu_h.cmd_start(msg, state, conn)
    check("/start показывает меню с балансом", "Добро пожаловать" in msg.last
          and "0.00" in msg.last)

    # --------------------------------------------------------- пополнение
    call = FakeCallback("dep:card", bot=bot)
    await dep_h.cb_card(call, state)
    check("пополнение спрашивает сумму", "Введите сумму" in call.last)

    msg = FakeMessage("abc", bot=bot)
    await dep_h.on_amount(msg, state)
    check("нечисловая сумма отклоняется", "Введите сумму числом" in msg.last)

    msg = FakeMessage("5", bot=bot)
    await dep_h.on_amount(msg, state)
    check("сумма ниже минимума отклоняется", "Минимальная сумма" in msg.last)

    msg = FakeMessage("100", bot=bot)
    await dep_h.on_amount(msg, state)
    check("выдаются реквизиты Душанбе", "Душанбе" in msg.last and "100.00" in msg.last)
    check("состояние ждёт чек", await state.get_state() == "Deposit:receipt")

    msg = FakeMessage("вот перевёл", bot=bot)
    await dep_h.on_receipt_wrong(msg)
    check("текст вместо чека не принимается", "фото или файл" in msg.last)

    msg = FakeMessage(photo=True, bot=bot)
    await dep_h.on_receipt(msg, state, conn, bot)
    pending = await db.list_deposits(conn, status=db.DEP_PENDING)
    check("заявка на пополнение создана", len(pending) == 1
          and pending[0].amount == 10000, fmt(pending[0].amount) if pending else "—")

    # админ подтверждает
    from app.handlers.admin import _resolve_deposit
    report = await _resolve_deposit(conn, bot, pending[0].id, 111, approved=True)
    user = await db.get_user(conn, USER_ID)
    check("после подтверждения баланс пополнен", user.balance == 10000, fmt(user.balance))
    check("повторное подтверждение не проходит",
          "уже обработана" in await _resolve_deposit(conn, bot, pending[0].id, 111, approved=True))

    # ------------------------------------------------------- покупка звёзд
    call = FakeCallback("stars:buy", bot=bot)
    await shop_h.cb_stars_buy(call, state, conn)
    check("показан курс и доступное количество",
          "Введите количество" in call.last and "500 звёзд" in call.last)

    msg = FakeMessage("10", bot=bot)
    await shop_h.on_quantity(msg, state, conn)
    check("количество ниже минимума отклоняется", "целое число" in msg.last)

    msg = FakeMessage("99999", bot=bot)
    await shop_h.on_quantity(msg, state, conn)
    check("количество выше максимума отклоняется", "целое число" in msg.last)

    msg = FakeMessage("100", bot=bot)
    await shop_h.on_quantity(msg, state, conn)
    check("корректное количество ведёт к вводу получателя",
          "username" in msg.last.lower())

    msg = FakeMessage("не юзернейм!", bot=bot)
    await shop_h.on_recipient(msg, state, conn, provider)
    check("кривой юзернейм отклоняется", "Не похоже на юзернейм" in msg.last)

    msg = FakeMessage("@notfound", bot=bot)
    await shop_h.on_recipient(msg, state, conn, provider)
    check("несуществующий получатель отклоняется", "не найден" in msg.last)

    msg = FakeMessage("https://t.me/target_user", bot=bot)
    await shop_h.on_recipient(msg, state, conn, provider)
    check("ссылка t.me распознаётся как юзернейм",
          "Проверьте получателя" in msg.last and "@target_user" in msg.last)
    check("показывается ИМЯ аккаунта, а не только юзернейм",
          "Target_user Test" in msg.last, msg.last.replace("\n", " ")[:110])
    check("чужой аккаунт помечен предупреждением", "чужой" in msg.last)
    check("состояние ждёт подтверждения получателя",
          await state.get_state() == "Buy:check_recipient")

    call = FakeCallback("order:recipient_ok", bot=bot)
    await shop_h.cb_recipient_ok(call, state, conn)
    check("после подтверждения показывается сводка заказа",
          "Подтверждение заказа" in call.last)
    check("в сводке верная сумма и остаток",
          "20.00" in call.last and "80.00" in call.last,
          call.last.replace("\n", " ")[:100])

    call = FakeCallback("order:go", bot=bot)
    await shop_h.cb_pay(call, state, conn, provider, bot)
    user = await db.get_user(conn, USER_ID)
    orders = await db.list_orders(conn, user_id=USER_ID)
    check("звёзды отправлены получателю", provider.delivered == [("target_user", 100)],
          str(provider.delivered))
    check("баланс списан", user.balance == 8000, fmt(user.balance))
    check("заказ выполнен", orders and orders[0].status == db.ORDER_DELIVERED)
    check("покупателю пришло подтверждение",
          any("выполнен" in text for _, text in bot.messages))

    # ------------------------------------------------- покупка без денег
    call = FakeCallback("stars:buy", bot=bot)
    await shop_h.cb_stars_buy(call, state, conn)
    msg = FakeMessage("10000", bot=bot)
    await shop_h.on_quantity(msg, state, conn)
    check("покупка сверх баланса блокируется до списания",
          "Недостаточно средств" in msg.last)

    # ------------------------------------------------------------ профиль
    call = FakeCallback("m:profile", bot=bot)
    await prof_h.cb_profile(call, state, conn)
    check("профиль показывает баланс и статистику",
          "80.00" in call.last and "Всего куплено звёзд" in call.last
          and "100" in call.last)

    call = FakeCallback("p:history", bot=bot)
    await prof_h.cb_history(call, conn)
    check("история покупок не пустая", "@target_user" in call.last)

    call = FakeCallback("p:ref", bot=bot)
    await prof_h.cb_referral(call, conn)
    check("реферальная ссылка сформирована", f"ref{USER_ID}" in call.last)

    # ---------------------------------------------------------- калькулятор
    msg = FakeMessage("500", bot=bot)
    await menu_h.on_calc(msg)
    check("калькулятор считает стоимость звёзд", "100.00" in msg.last, msg.last)

    msg = FakeMessage("50с", bot=bot)
    await menu_h.on_calc(msg)
    check("калькулятор считает звёзды за сумму", "250" in msg.last, msg.last)

    # ------------------------------------------------------------ поддержка
    call = FakeCallback("m:support", bot=bot)
    await sup_h.cb_support(call, state, conn)
    check("раздел поддержки открывается", "Техническая поддержка" in call.last)

    call = FakeCallback("t:new", bot=bot)
    await sup_h.cb_new_ticket(call, state, conn)
    msg = FakeMessage("Не пришли звёзды по заказу 1", bot=bot)
    await sup_h.on_subject(msg, state, conn, bot)
    tickets = await db.list_tickets(conn, status=db.TICKET_OPEN)
    check("тикет создан", len(tickets) == 1 and "Тикет №" in msg.last)

    call = FakeCallback("t:new", bot=bot)
    await sup_h.cb_new_ticket(call, state, conn)
    check("второй тикет при открытом первом не создаётся",
          any("уже есть открытый" in alert for alert in call.alerts))


asyncio.run(main())
