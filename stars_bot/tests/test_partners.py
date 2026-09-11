"""Партнёры: доли прибыли, взносы, выплаты и что у кого на руках."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_fixture  # noqa: F401

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Chat, Message, User
from pydantic import PrivateAttr

from app import db, runtime
from app.handlers import panel
from app.money import fmt

ADMIN = 111
PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  — {detail}" if detail else ""))


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
    def markup(self):
        return self.message.markup

    @property
    def alerts(self) -> list:
        return self._alerts


def msg(text=None) -> SpyMessage:
    user = User(id=ADMIN, is_bot=False, first_name="Админ", username="admin")
    return SpyMessage.model_construct(
        message_id=1, date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        chat=Chat(id=ADMIN, type="private"), from_user=user, text=text,
    )


def call_of(data: str) -> SpyCallback:
    user = User(id=ADMIN, is_bot=False, first_name="Админ", username="admin")
    return SpyCallback.model_construct(
        id="1", from_user=user, chat_instance="x", data=data, message=msg(),
    )


def buttons(markup) -> list[str]:
    return [b.text for row in markup.inline_keyboard for b in row]


async def sale(conn, price: int, cost: int, user_id: int = 900) -> None:
    order = await db.create_order(
        conn, user_id=user_id, product_type="stars", quantity=100,
        recipient="kto", price=price, cost=cost,
    )
    await db.update_order(conn, order.id, status=db.ORDER_DELIVERED)


async def run(conn) -> None:
    storage = MemoryStorage()
    state = FSMContext(storage=storage,
                       key=StorageKey(bot_id=1, chat_id=ADMIN, user_id=ADMIN))
    await db.upsert_user(conn, 900, "klient", "Клиент")

    # ------------------------------------------------ пустой раздел
    call = call_of("pn:partners")
    await panel.cb_partners(call, state, conn)
    check("раздел открывается", "Партнёры" in call.last)
    check("пустой список объясняется", "Партнёров пока нет" in call.last)
    check("есть кнопка добавления", "➕ Добавить партнёра" in buttons(call.markup))

    # ------------------------------------------------ добавление
    call = call_of("pn:pt_new")
    await panel.cb_partner_new(call, state)
    check("спрашивает имя", "Пришлите имя" in call.last)
    check("ждём имя", await state.get_state() == "PartnerNew:name")

    short = msg("я")
    await panel.on_partner_name(short, state)
    check("слишком короткое имя отклонено", "❌" in short.last)

    await panel.on_partner_name(msg("Алиджон"), state)
    check("спрашивает долю", await state.get_state() == "PartnerNew:share")

    bad = msg("сто")
    await panel.on_partner_share(bad, state, conn)
    check("нечисловая доля отклонена", "❌" in bad.last)
    over = msg("150")
    await panel.on_partner_share(over, state, conn)
    check("доля больше 100 отклонена", "❌" in over.last)

    done = msg("60")
    await panel.on_partner_share(done, state, conn)
    partners = await db.list_partners(conn)
    check("партнёр создан", len(partners) == 1 and partners[0].name == "Алиджон")
    check("доля сохранена", partners[0].share == 60, str(partners[0].share))
    check("шаг закрыт", await state.get_state() is None)

    # второй партнёр
    await panel.cb_partner_new(call_of("pn:pt_new"), state)
    await panel.on_partner_name(msg("Напарник"), state)
    await panel.on_partner_share(msg("40"), state, conn)
    check("второй партнёр добавлен", len(await db.list_partners(conn)) == 2)

    # ------------------------------------------------ деление прибыли
    await sale(conn, price=100_00, cost=80_00)     # прибыль 20.00
    await sale(conn, price=200_00, cost=170_00)    # прибыль 30.00
    money = await db.total_profit(conn)
    check("прибыль считается из заказов", money["profit"] == 50_00, str(money))
    check("выручка отдельно", money["revenue"] == 300_00, str(money))

    call = call_of("pn:partners")
    await panel.cb_partners(call, state, conn)
    check("доля первого верна", "Заработал: <b>30.00 с.</b>" in call.last, call.last)
    check("доля второго верна", "Заработал: <b>20.00 с.</b>" in call.last, call.last)
    check("общая прибыль показана", "Общая прибыль: 50.00 с." in call.last)
    check("предупреждения о долях нет", "должно быть 100" not in call.last)

    # отменённый заказ в прибыль не идёт
    refunded = await db.create_order(
        conn, user_id=900, product_type="stars", quantity=100,
        recipient="kto", price=500_00, cost=400_00,
    )
    await db.update_order(conn, refunded.id, status=db.ORDER_REFUNDED)
    check("возврат в прибыль не попал",
          (await db.total_profit(conn))["profit"] == 50_00)

    # ------------------------------------------------ взносы и выплаты
    first = (await db.list_partners(conn))[0]
    call = call_of(f"pn:pt_in:{first.id}")
    await panel.cb_partner_in(call, state, conn)
    check("спрашивает сумму взноса", "внёс в оборот" in call.last, call.last[:80])
    check("ждём сумму", await state.get_state() == "PartnerMove:amount")

    bad = msg("много")
    await panel.on_partner_amount(bad, state, conn)
    check("нечисловая сумма отклонена", "❌" in bad.last)

    await panel.on_partner_amount(msg("500 пополнил FazerCards"), state, conn)
    totals = await db.partner_totals(conn, first.id)
    check("взнос записан", totals["put_in"] == 500_00, str(totals))
    check("примечание сохранено",
          (await db.partner_moves(conn, first.id))[0]["note"] == "пополнил FazerCards")

    call = call_of(f"pn:pt_out:{first.id}")
    await panel.cb_partner_out(call, state, conn)
    check("спрашивает сумму выплаты", "забрал себе" in call.last)
    await panel.on_partner_amount(msg("200"), state, conn)
    totals = await db.partner_totals(conn, first.id)
    check("выплата записана", totals["took_out"] == 200_00, str(totals))
    check("взнос при этом не изменился", totals["put_in"] == 500_00)

    # на руках = доля прибыли + внёс − забрал = 30 + 500 − 200 = 330
    call = call_of(f"pn:pt:{first.id}")
    await panel.cb_partner_card(call, conn)
    check("на руках посчитано верно", "На руках: <b>330.00 с.</b>" in call.last,
          call.last)
    check("в карточке видна история", "Движение денег" in call.last)
    check("в истории видны и плюс, и минус",
          "+500.00" in call.last and "−200.00" in call.last, call.last)
    check("есть обе кнопки", "➕ Внёс в оборот" in buttons(call.markup)
          and "➖ Забрал себе" in buttons(call.markup))

    # ------------------------------------------------ правка доли
    call = call_of(f"pn:pt_share:{first.id}")
    await panel.cb_partner_share(call, state, conn)
    check("экран правки доли", "Сейчас: <b>60%</b>" in call.last, call.last[:120])
    await panel.on_partner_share(msg("70"), state, conn)
    check("доля изменена", (await db.get_partner(conn, first.id)).share == 70)
    check("нового партнёра при этом не создалось",
          len(await db.list_partners(conn)) == 2)

    call = call_of("pn:partners")
    await panel.cb_partners(call, state, conn)
    check("сумма долей не 110 — предупреждаем",
          "должно быть 100" in call.last, call.last[-300:])

    # ------------------------------------------------ удаление
    call = call_of(f"pn:pt_del:{first.id}")
    await panel.cb_partner_delete(call, conn)
    check("партнёр убран из списка", len(await db.list_partners(conn)) == 1)
    check("история его движений сохранена",
          (await db.partner_totals(conn, first.id))["put_in"] == 500_00)
    check("карточка удалённого не падает", "Партнёры" in call.last)

    check("раздел есть в главном меню панели",
          any("Партнёры" in b.text for r in panel.home_kb().inline_keyboard for b in r))


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
