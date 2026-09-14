"""Игры: цены пакетов, проверка ID, заказ, присмотр и возврат по таймауту."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
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
from app.handlers import games as gh
from app.handlers import panel
from app.money import fmt
from app.services import games as svc
from app.services import nicknames
from app.services.fragment import DeliveryError, DeliveryProvider, DeliveryUncertain

BUYER = 777
ADMIN = 111
PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  — {detail}" if detail else ""))


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))

    def to(self, chat_id):
        return [t for cid, t in self.sent if cid == chat_id]


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


def msg(text=None, uid=BUYER) -> SpyMessage:
    user = User(id=uid, is_bot=False, first_name="Игрок", username="gamer")
    return SpyMessage.model_construct(
        message_id=1, date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        chat=Chat(id=uid, type="private"), from_user=user, text=text,
    )


def call_of(data: str, uid=BUYER) -> SpyCallback:
    user = User(id=uid, is_bot=False, first_name="Игрок", username="gamer")
    return SpyCallback.model_construct(
        id="1", from_user=user, chat_instance="x", data=data, message=msg(uid=uid),
    )


def buttons(markup) -> list[str]:
    return [b.text for row in markup.inline_keyboard for b in row]


class GameProvider(DeliveryProvider):
    """Поставщик игр: по умолчанию принимает заказ и держит его в обработке."""

    def __init__(self, *, validate=("Ник", "ok"), status="processing",
                 order_error=None):
        self.validate_reply = validate
        self.status = status
        self.order_error = order_error
        self.orders: list[dict] = []
        self.idempotency: list[str] = []

    async def game_offers(self, category_id):
        return [
            {"offer_id": "off_1", "name": "100 алмазов",
             "usd": Decimal("1.00"), "raw": {}},
            {"offer_id": "off_2", "name": "500 алмазов",
             "usd": Decimal("4.50"), "raw": {}},
        ]

    async def validate_game_id(self, category_id, fields):
        return self.validate_reply

    async def order_game(self, *, category_id, offer_id, fields, quantity,
                         idempotency_key):
        if self.order_error:
            raise self.order_error
        self.idempotency.append(idempotency_key)
        self.orders.append({"category_id": category_id, "offer_id": offer_id,
                            "fields": fields, "quantity": quantity})
        return {"order_id": "ord-906267", "status": "processing"}

    async def order_status(self, order_id):
        return {"order_id": order_id, "status": self.status}


# ─────────────────────────────────────────────────────── цены и ключи


async def pricing(conn) -> None:
    await runtime.set_value(conn, "usd_rate_diram", "1090")   # 10.90 с. за $
    await runtime.set_value(conn, "margin_percent", "20")
    await runtime.set_value(conn, "round_prices", "up1")

    # $1.00 × 10.90 = 10.90 с., +20% = 13.08 с., округление вверх → 14.00 с.
    price = svc.offer_price(Decimal("1.00"), 20)
    check("цена пакета = себестоимость × наценка, округлённая",
          price == 1400, str(price))
    check("себестоимость считается по курсу",
          svc.offer_cost(Decimal("1.00")) == 1090, str(svc.offer_cost(Decimal("1"))))

    await runtime.set_value(conn, "usd_rate_diram", "0")
    check("без курса цены нет", svc.offer_price(Decimal("1.00"), 20) == 0)
    await runtime.set_value(conn, "usd_rate_diram", "1090")

    game = db.Game(category_id="x", title="X", field="user_id", region="",
                   margin=0, enabled=1, created_at="")
    check("без своей наценки берётся общая", svc.margin_of(game) == 20)
    game.margin = 35
    check("своя наценка важнее общей", svc.margin_of(game) == 35)

    keys = {svc.idempotency_key(n) for n in range(50)}
    check("ключ идемпотентности уникален на заказ", len(keys) == 50)
    check("ключ одного заказа не меняется",
          svc.idempotency_key(7) == svc.idempotency_key(7))


# ────────────────────────────────────────────────────────── ники


async def nick_lookup() -> None:
    nicknames.forget_all()

    class Resp:
        def __init__(self, payload, status=200):
            self.payload, self.status = payload, status

        async def json(self, content_type=None):
            return self.payload

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    calls = []

    class Session:
        def __init__(self, reply):
            self.reply = reply

        def get(self, url, headers=None):
            calls.append(url)
            return self.reply

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    real = nicknames.aiohttp.ClientSession
    nicknames.aiohttp.ClientSession = lambda *a, **kw: Session(
        Resp({"AccountInfo": {"AccountName": "ProPlayer", "AccountLevel": 70}})
    )
    found = await nicknames.free_fire("1724367212", key="k", region="BR")
    check("ник получен", found.name == "ProPlayer" and found.verdict == "ok",
          str(found))
    check("регион ушёл в запрос", "region=BR" in calls[-1], calls[-1])

    before = len(calls)
    again = await nicknames.free_fire("1724367212", key="k", region="BR")
    check("повтор берётся из кэша", again.source == "кэш", again.source)
    check("лимит при этом не тратится", len(calls) == before, str(len(calls)))

    nicknames.aiohttp.ClientSession = lambda *a, **kw: Session(Resp({}, status=402))
    bad = await nicknames.free_fire("999", key="k")
    check("402 — это «неверный ID»", bad.verdict == "bad", str(bad))

    nicknames.aiohttp.ClientSession = lambda *a, **kw: Session(Resp({}, status=429))
    over = await nicknames.free_fire("555", key="k")
    check("429 не считается неверным ID", over.verdict == "unknown", str(over))
    check("неудача не кэшируется", nicknames.cached("555") is None)

    nicknames.aiohttp.ClientSession = real


# ───────────────────────────────────────────────────── покупка


async def flow(conn) -> None:
    storage = MemoryStorage()
    state = FSMContext(storage=storage,
                       key=StorageKey(bot_id=1, chat_id=BUYER, user_id=BUYER))
    provider = GameProvider()
    bot = FakeBot()

    await db.upsert_user(conn, BUYER, "gamer", "Игрок")
    await db.credit(conn, BUYER, 200_00, as_deposit=True)
    game = await db.add_game(conn, category_id="free_fire_br",
                             title="🔥 Free Fire", region="BR")
    await db.update_game(conn, game.category_id, enabled=1)
    await db.load_game_titles(conn)
    game = await db.get_game(conn, "free_fire_br")

    check("игра стала товаром", game.product_type == "game:free_fire_br")
    check("у товара человеческое название",
          db.product_title(game.product_type) == "🔥 Free Fire")

    call = call_of("m:games")
    await gh.cb_games(call, state, conn)
    check("раздел игр открывается", "Пополнение игр" in call.last)
    check("сказано, что пароль не нужен", "пароль" in call.last.lower())
    check("игра показана кнопкой", "🔥 Free Fire" in buttons(call.markup))

    # Steam и игры — за одной кнопкой меню
    await runtime.set_value(conn, "steam_price_e4", "1400")
    await runtime.set_value(conn, "steam_enabled", "1")
    check("в меню один вход на игры и Steam",
          sum("Игры и Steam" in b for b in buttons(keyboards.main_menu(games=True))) == 1,
          str(buttons(keyboards.main_menu(games=True))))
    check("отдельной кнопки Steam в меню нет",
          not any(b.strip().endswith("Пополнить Steam")
                  for b in buttons(keyboards.main_menu(games=True))))

    call = call_of("m:games")
    await gh.cb_games(call, state, conn)
    inner = buttons(call.markup)
    check("внутри раздела есть Steam", any("Steam" in b for b in inner), str(inner))
    check("и обе игры", "🔥 Free Fire" in inner, str(inner))

    # только Steam, без игр — раздел всё равно открывается
    await db.update_game(conn, "free_fire_br", enabled=0)
    call = call_of("m:games")
    await gh.cb_games(call, state, conn)
    check("с одним Steam раздел работает",
          any("Steam" in b for b in buttons(call.markup)), str(buttons(call.markup)))
    await db.update_game(conn, "free_fire_br", enabled=1)
    await runtime.set_value(conn, "steam_enabled", "0")

    call = call_of("g:free_fire_br")
    await gh.cb_game(call, state, conn, provider)
    check("пакеты показаны", "Выберите пакет" in call.last, call.last[:80])
    labels = buttons(call.markup)
    check("на кнопке пакет и цена в сомони",
          "100 алмазов — 14.00 с." in labels, str(labels))
    check("дорогой пакет тоже посчитан",
          "500 алмазов — 59.00 с." in labels, str(labels))

    call = call_of("gp:free_fire_br:0")
    await gh.cb_pack(call, state, conn)
    check("бот просит ID", "ID игрока" in call.last, call.last[:80])
    check("ждём ID", await state.get_state() == "Game:player")

    bad = msg("abc")
    await gh.on_player_id(bad, state, conn, provider)
    check("нечисловой ID отклонён", "Такого игрока нет" in bad.last)

    good = msg("1724367212")
    await gh.on_player_id(good, state, conn, provider)
    check("ник показан на подтверждение", "Проверьте аккаунт" in good.last)
    check("виден ник игрока", "Ник" in good.last, good.last[:200])
    check("виден ID", "1724367212" in good.last)
    check("предупреждение о необратимости", "вернуть его будет" in good.last)
    check("ждём подтверждения", await state.get_state() == "Game:confirm")

    call = call_of("g:ok")
    await gh.cb_buy(call, state, conn, provider, bot)

    check("заказ ушёл поставщику", len(provider.orders) == 1, str(provider.orders))
    sent = provider.orders[0]
    check("в заказе верная игра", sent["category_id"] == "free_fire_br")
    check("в заказе верный пакет", sent["offer_id"] == "off_1")
    check("в заказе ID игрока", sent["fields"] == {"user_id": "1724367212"})
    check("ключ идемпотентности передан", len(provider.idempotency) == 1)

    user = await db.get_user(conn, BUYER)
    check("деньги списаны", user.balance == 200_00 - 1400, fmt(user.balance))
    order = (await db.list_orders(conn, user_id=BUYER))[0]
    check("заказ записан как игровой",
          order.product_type == "game:free_fire_br", order.product_type)
    check("номер у поставщика сохранён", order.fragment_order_id == "ord-906267")
    check("себестоимость записана", order.cost == 1090, str(order.cost))
    check("прибыль с игры считается", order.profit == 1400 - 1090, str(order.profit))
    check("заказ ещё в работе", order.status == db.ORDER_DELIVERING, order.status)
    said = [t for t, _ in call.message._log]
    check("клиенту сказано, что заказ принят",
          any("принят" in t for t in said), str(said[-2:]))
    check("и что нужно подождать", any("несколько минут" in t for t in said))

    # ------------------------------------------------ доглядчик доводит до конца
    provider.status = "completed"
    result = await svc.check(bot, conn, provider, order)
    check("доглядчик видит выполнение", result == "done", result)
    order = await db.get_order(conn, order.id)
    check("заказ закрыт как выполненный", order.status == db.ORDER_DELIVERED)
    done = [t for t in bot.to(BUYER) if "выполнен" in t]
    check("клиенту пришло сообщение о выдаче", bool(done), str(bot.to(BUYER)))
    check("в нём ID игрока", done and "1724367212" in done[0])

    # ------------------------------------------------ отказ поставщика
    provider = GameProvider(order_error=DeliveryError("INSUFFICIENT_BALANCE"))
    bot = FakeBot()
    await state.set_state(gh.Game.confirm)
    await state.update_data(category_id="free_fire_br", offer_id="off_1",
                            pack="100 алмазов", price=1400, cost=1090,
                            player="1724367212", player_name="Ник")
    before = (await db.get_user(conn, BUYER)).balance
    call = call_of("g:ok")
    await gh.cb_buy(call, state, conn, provider, bot)
    check("при отказе деньги возвращаются",
          (await db.get_user(conn, BUYER)).balance == before, fmt(before))
    check("владельцу сказали о нехватке баланса",
          any("INSUFFICIENT_BALANCE" in t for t in bot.to(ADMIN)), str(bot.to(ADMIN)))
    check("клиенту сказали о возврате", "не выполнен" in call.last, call.last[:80])

    # ------------------------------------------------ возврат по таймауту
    provider = GameProvider(status="processing")
    bot = FakeBot()
    stuck = await db.create_order(
        conn, user_id=BUYER, product_type="game:free_fire_br", quantity=1,
        recipient="1724367212", price=1400, cost=1090,
    )
    await db.update_order(conn, stuck.id, fragment_order_id="ord-old")
    old = (datetime.now(timezone.utc) - timedelta(minutes=25)).isoformat(timespec="seconds")
    await conn.execute("UPDATE orders SET created_at = ? WHERE id = ?", (old, stuck.id))
    await conn.commit()
    stuck = await db.get_order(conn, stuck.id)

    before = (await db.get_user(conn, BUYER)).balance
    result = await svc.check(bot, conn, provider, stuck)
    check("зависший заказ закрывается возвратом", result == "timeout", result)
    check("деньги вернулись клиенту",
          (await db.get_user(conn, BUYER)).balance == before + 1400)
    check("заказ помечен возвращённым",
          (await db.get_order(conn, stuck.id)).status == db.ORDER_REFUNDED)
    warn = [t for t in bot.to(ADMIN) if "висел" in t]
    check("владельца предупредили", bool(warn), str(bot.to(ADMIN)))
    check("в предупреждении номер у поставщика",
          warn and "ord-old" in warn[0], str(warn[:1]))

    # свежий заказ в обработке не трогаем
    fresh = await db.create_order(
        conn, user_id=BUYER, product_type="game:free_fire_br", quantity=1,
        recipient="1", price=1400, cost=1090,
    )
    await db.update_order(conn, fresh.id, fragment_order_id="ord-new")
    result = await svc.check(bot, conn, provider, await db.get_order(conn, fresh.id))
    check("свежий заказ продолжает ждать", result == "waiting", result)
    check("деньги за него не вернулись",
          (await db.get_order(conn, fresh.id)).status == db.ORDER_DELIVERING)

    pending = await db.unfinished_game_orders(conn)
    check("незавершённые заказы находятся", any(o.id == fresh.id for o in pending))
    check("завершённых среди них нет",
          all(o.status in (db.ORDER_DELIVERING, db.ORDER_FAILED) for o in pending))


# ────────────────────────────────────────────── ID без ника не блокирует


async def unknown_nick(conn) -> None:
    storage = MemoryStorage()
    state = FSMContext(storage=storage,
                       key=StorageKey(bot_id=1, chat_id=BUYER, user_id=BUYER))
    provider = GameProvider(validate=(None, "unknown"))
    nicknames.forget_all()

    real = nicknames.free_fire

    async def silent(uid, key="", region=""):
        return nicknames.Nickname(uid=uid, name=None, verdict="unknown")

    nicknames.free_fire = silent
    try:
        await state.set_state(gh.Game.player)
        await state.update_data(category_id="free_fire_br", offer_id="off_1",
                                pack="100 алмазов", price=1400, cost=1090)
        message = msg("5555555555")
        await gh.on_player_id(message, state, conn, provider)
        check("без ника покупку не блокируем", "ID принят" in message.last,
              message.last[:80])
        check("но просим проверить ID самому",
              "проверьте ID сами" in message.last, message.last)
        check("до подтверждения всё равно доходит",
              await state.get_state() == "Game:confirm")

        # явный отказ — другое дело
        provider.validate_reply = (None, "bad")
        await state.set_state(gh.Game.player)
        message = msg("4444444444")
        await gh.on_player_id(message, state, conn, provider)
        check("неверный ID покупку блокирует",
              "Такого игрока нет" in message.last, message.last[:80])
    finally:
        nicknames.free_fire = real


# ─────────────────────────────────────────────────────────── панель


async def panel_screens(conn) -> None:
    state = FSMContext(storage=MemoryStorage(),
                       key=StorageKey(bot_id=1, chat_id=ADMIN, user_id=ADMIN))
    call = call_of("pn:games", uid=ADMIN)
    await panel.cb_games(call, state, conn)
    check("раздел игр в панели открывается", "Игры" in call.last)
    check("игра видна", "Free Fire" in call.last)
    check("есть кнопка добавления", "➕ Добавить игру" in buttons(call.markup))

    call = call_of("pn:game_new", uid=ADMIN)
    await panel.cb_game_new(call, state)
    check("просит код и название", "код название" in call.last, call.last[:120])

    bad = msg("ЕРУНДА", uid=ADMIN)
    await panel.on_game_new(bad, state, conn)
    check("кривой формат отклонён", "❌" in bad.last)

    good = msg("pubg_mobile 🎯 PUBG Mobile", uid=ADMIN)
    await panel.on_game_new(good, state, conn)
    pubg = await db.get_game(conn, "pubg_mobile")
    check("вторая игра добавлена", pubg is not None and pubg.title == "🎯 PUBG Mobile")
    check("новая игра сразу не продаётся", pubg.enabled == 0)

    call = call_of("pn:game_on:pubg_mobile", uid=ADMIN)
    await panel.cb_game_toggle(call, conn)
    check("игра включается", (await db.get_game(conn, "pubg_mobile")).enabled == 1)

    call = call_of("pn:game_packs:free_fire_br", uid=ADMIN)
    await panel.cb_game_offers(call, conn, GameProvider())
    check("пакеты показаны владельцу", "100 алмазов" in call.last, call.last[:200])
    check("рядом видна себестоимость", "себестоимость" in call.last)

    call = call_of("pn:game_margin:free_fire_br", uid=ADMIN)
    await panel.cb_game_margin(call, state, conn)
    await panel.on_field_value(msg("35", uid=ADMIN), state, conn)
    check("своя наценка сохранена",
          (await db.get_game(conn, "free_fire_br")).margin == 35)

    call = call_of("pn:game_del:pubg_mobile", uid=ADMIN)
    await panel.cb_game_delete(call, conn)
    check("игра удаляется", await db.get_game(conn, "pubg_mobile") is None)

    check("раздел есть в главном меню панели",
          any("Игры" in b.text for r in panel.home_kb().inline_keyboard for b in r))
    check("кнопка балансов ключей есть",
          any("Балансы ключей" in b.text
              for r in panel.home_kb().inline_keyboard for b in r))

    await key_balances(conn)

    # игру можно закрепить за партнёром
    partner = await db.create_partner(conn, "Напарник", 0)
    await db.set_product_owner(conn, "game:free_fire_br", partner.id)
    rows = await db.sales_by_product(conn)
    ff = next((r for r in rows if r["product_type"] == "game:free_fire_br"), None)
    check("продажи игры видны отдельным товаром", ff is not None, str(rows))
    check("у него название игры", ff and ff["title"] == "🔥 Free Fire")
    check("игра закреплена за партнёром",
          (await db.product_owners(conn)).get("game:free_fire_br") == partner.id)


async def key_balances(conn) -> None:
    """Экран балансов: деньги поставщика и лимит сервиса ников."""
    from app.services import nicknames as nk

    class Rich(DeliveryProvider):
        async def get_balance(self):
            return "119.40 USD"

    class Broken(DeliveryProvider):
        async def get_balance(self):
            raise DeliveryError("HTTP 401: ключ не принят")

    await runtime.set_value(conn, "usd_rate_diram", "1090")
    await runtime.set_value(conn, "gameskinbo_key", "kluch")

    real = nk.usage

    async def usage(key):
        return {"used": 10, "limit": 100, "remaining": 90, "plan": "free"}

    nk.usage = usage
    try:
        call = call_of("pn:keys", uid=ADMIN)
        await panel.cb_keys(call, Rich())
        check("баланс поставщика показан", "119.40 USD" in call.last, call.last[:200])
        check("он пересчитан в сомони", "1 301.46" in call.last, call.last[:300])
        check("виден остаток лимита ников", "Осталось: <b>90</b>" in call.last,
              call.last)

        async def spent(key):
            return {"used": 95, "limit": 100, "remaining": 5, "plan": "free"}

        nk.usage = spent
        call = call_of("pn:keys", uid=ADMIN)
        await panel.cb_keys(call, Rich())
        check("малый остаток помечен другим цветом", "🟠" in call.last, call.last)

        call = call_of("pn:keys", uid=ADMIN)
        await panel.cb_keys(call, Broken())
        check("отказ поставщика виден", "не ответил" in call.last, call.last[:200])
        check("и причина показана", "401" in call.last)

        await runtime.set_value(conn, "gameskinbo_key", "")
        call = call_of("pn:keys", uid=ADMIN)
        await panel.cb_keys(call, Rich())
        check("без ключа ников так и сказано",
              "ключ не задан" in call.last, call.last[-300:])
    finally:
        nk.usage = real


async def main() -> None:
    for sfx in ("", "-wal", "-shm"):
        Path(str(db.settings.db_file) + sfx).unlink(missing_ok=True)
    conn = await db.connect()
    try:
        await db.init(conn)
        await runtime.load(conn)
        await pricing(conn)
        await nick_lookup()
        await flow(conn)
        await unknown_nick(conn)
        await panel_screens(conn)
    finally:
        await conn.close()
    print(f"\n{'=' * 52}\nПройдено: {len(PASS)}   Провалено: {len(FAIL)}")
    if FAIL:
        print("ПРОВАЛЫ:", ", ".join(FAIL))
    sys.exit(1 if FAIL else 0)


asyncio.run(main())
