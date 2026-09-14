"""Покупка игровых пополнений: выбор пакета, проверка ID, заказ."""
from __future__ import annotations

import logging
import re

import aiosqlite
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app import db, keyboards, runtime, texts
from app.money import fmt
from app.services import games as svc
from app.services import suppliers
from app.services import nicknames
from app.services.fragment import DeliveryError, DeliveryProvider, DeliveryUncertain
from app.states import Game

log = logging.getLogger(__name__)
router = Router(name="games")

#: Пакеты живут недолго в памяти: список одинаков для всех, а дёргать
#: поставщика на каждое нажатие незачем.
_offers: dict[str, list[dict]] = {}


async def offers_of(provider, game: db.Game, conn=None) -> list[dict]:
    """Пакеты игры с ценой в сомони.

    Своя цена, если она задана, важнее расчёта по наценке: владелец мог
    поставить ровную сумму или подстроиться под конкурента.
    """
    raw = await provider.game_offers(game.category_id)
    margin = svc.margin_of(game)
    manual = await db.game_prices(conn, game.category_id) if conn else {}

    offers = []
    for item in raw:
        auto = svc.offer_price(item["usd"], margin)
        own = manual.get(item["offer_id"])
        offers.append({
            "offer_id": item["offer_id"],
            "name": item["name"],
            "usd": item["usd"],
            "price": own if own is not None else auto,
            "auto": auto,
            "manual": own is not None,
            "cost": svc.offer_cost(item["usd"]),
        })
    offers = [o for o in offers if o["price"] > 0]
    _offers[game.category_id] = offers
    return offers


@router.callback_query(F.data == "m:games")
async def cb_games(
    call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection
) -> None:
    await state.clear()
    games = await db.list_games(conn, only_enabled=True)
    if not runtime.get_bool("games_enabled"):
        games = []
    if not games and not runtime.steam_on():
        await call.answer("Раздел временно закрыт.", show_alert=True)
        return
    await call.message.edit_text(
        texts.GAMES_ENTRY, reply_markup=keyboards.games_menu(games)
    )
    await call.answer()


@router.callback_query(F.data.startswith("g:"), ~F.data.in_({"g:ok"}))
async def cb_game(
    call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection,
    provider: DeliveryProvider,
) -> None:
    category_id = call.data.split(":", 1)[1]
    game = await db.get_game(conn, category_id)
    if game is None or not game.enabled:
        await call.answer("Эта игра больше не продаётся.", show_alert=True)
        return

    await call.answer("Смотрю пакеты…")
    provider = suppliers.for_games(provider)
    try:
        offers = await offers_of(provider, game, conn)
    except (DeliveryError, DeliveryUncertain) as exc:
        log.info("Игры: пакеты %s не пришли — %s", category_id, exc)
        await call.message.edit_text(
            "😔 Пакеты этой игры сейчас недоступны. Попробуйте позже.",
            reply_markup=keyboards.back(),
        )
        return

    if not offers:
        await call.message.edit_text(
            "😔 У этой игры пока нет пакетов в продаже.",
            reply_markup=keyboards.back(),
        )
        return

    await state.clear()
    await call.message.edit_text(
        texts.GAME_PACKS.format(title=game.title),
        reply_markup=keyboards.game_packs(category_id, offers),
    )


@router.callback_query(F.data.startswith("gp:"))
async def cb_pack(
    call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection
) -> None:
    _, category_id, raw_index = call.data.split(":", 2)
    game = await db.get_game(conn, category_id)
    offers = _offers.get(category_id) or []
    index = int(raw_index) if raw_index.isdigit() else -1

    if game is None or not 0 <= index < len(offers):
        await call.answer("Пакет устарел, откройте игру заново.", show_alert=True)
        return

    offer = offers[index]
    user = await db.get_user(conn, call.from_user.id)
    balance = user.balance if user else 0
    if balance < offer["price"]:
        await call.message.edit_text(
            texts.STARS_NOT_ENOUGH.format(
                need=fmt(offer["price"]), balance=fmt(balance),
                missing=fmt(offer["price"] - balance),
            ),
            reply_markup=keyboards.deposit_methods(),
        )
        await call.answer()
        return

    await state.set_state(Game.player)
    await state.update_data(
        category_id=category_id, offer_index=index,
        offer_id=offer["offer_id"], pack=offer["name"],
        price=offer["price"], cost=offer["cost"],
    )
    await call.message.edit_text(
        texts.GAME_ASK_ID.format(title=game.title, pack=offer["name"]),
        reply_markup=keyboards.cancel(),
    )
    await call.answer()


@router.message(Game.player, F.text)
async def on_player_id(
    message: Message, state: FSMContext, conn: aiosqlite.Connection,
    provider: DeliveryProvider,
) -> None:
    player = (message.text or "").strip()
    if not re.fullmatch(r"\d{5,20}", player):
        await message.answer(texts.GAME_BAD_ID.format(player=player[:20] or "—"))
        return

    data = await state.get_data()
    game = await db.get_game(conn, data.get("category_id", ""))
    if game is None:
        await state.clear()
        await message.answer("Игра больше не продаётся. Откройте меню: /menu")
        return

    notice = await message.answer(texts.GAME_CHECKING.format(player=player))
    name, verdict = await _lookup(suppliers.for_games(provider), game, player)

    if verdict == "bad":
        await notice.edit_text(texts.GAME_BAD_ID.format(player=player))
        return

    user = await db.get_user(conn, message.from_user.id)
    balance = user.balance if user else 0
    price = data["price"]
    await state.update_data(player=player, player_name=name or "")
    await state.set_state(Game.confirm)

    template = texts.GAME_CONFIRM if name else texts.GAME_NO_NAME
    await notice.edit_text(
        template.format(
            name=name or "—", player=player, pack=data["pack"],
            price=fmt(price), rest=fmt(max(balance - price, 0)),
        ),
        reply_markup=keyboards.confirm_game(game.category_id),
    )


async def _lookup(provider, game: db.Game, player: str) -> tuple[str | None, str]:
    """Ник игрока. Сначала сервис выдачи, для Free Fire — отдельный источник.

    Блокируем покупку только на явном «такого игрока нет». Если ник просто
    не пришёл — продаём: пополнение идёт по ID, ник нужен для сверки глазами.
    """
    name, verdict = await provider.validate_game_id(
        game.category_id, {game.field: player}
    )
    if verdict == "ok" and name:
        return name, "ok"
    if verdict == "bad":
        return None, "bad"

    if "free_fire" in game.category_id or "freefire" in game.category_id:
        key = runtime.get("gameskinbo_key") or db.settings.gameskinbo_key
        found = await nicknames.free_fire(player, key=key, region=game.region)
        if found.verdict == "ok":
            return found.name, "ok"
        if found.verdict == "bad":
            return None, "bad"
    return None, "unknown"


@router.callback_query(Game.confirm, F.data == "g:ok")
async def cb_buy(
    call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection,
    provider: DeliveryProvider, bot: Bot,
) -> None:
    from app.handlers.menu import main_markup
    from app.services import delivery

    data = await state.get_data()
    game = await db.get_game(conn, data.get("category_id", ""))
    if game is None:
        await state.clear()
        await call.answer("Игра больше не продаётся.", show_alert=True)
        return
    await state.clear()
    # Игры списываются с того счёта, чей ключ задан для игр.
    provider = suppliers.for_games(provider)

    if not await db.charge(conn, call.from_user.id, data["price"]):
        user = await db.get_user(conn, call.from_user.id)
        balance = user.balance if user else 0
        await call.message.edit_text(
            texts.STARS_NOT_ENOUGH.format(
                need=fmt(data["price"]), balance=fmt(balance),
                missing=fmt(data["price"] - balance),
            ),
            reply_markup=keyboards.deposit_methods(),
        )
        await call.answer()
        return

    order = await db.create_order(
        conn, user_id=call.from_user.id, product_type=game.product_type,
        quantity=1, recipient=data["player"],
        price=data["price"], cost=data.get("cost", 0),
    )
    await call.answer()

    try:
        external = await svc.place(
            provider, game=game, offer_id=data["offer_id"],
            player_id=data["player"], quantity=1, order_id=order.id,
        )
    except DeliveryError as exc:
        # Явный отказ — выдачи не было, возвращаем деньги сразу.
        await svc._refund(bot, conn, order, str(exc))

        # Поставщик сам называет поле, которого ему не хватило. Запоминаем
        # его, чтобы следующий заказ по этой игре ушёл правильно.
        fixed = ""
        wanted = svc.missing_field(str(exc))
        if wanted and wanted != game.field:
            await db.update_game(conn, game.category_id, field=wanted)
            fixed = (f"\n\n✅ <b>Поле исправлено:</b> <code>{game.field}</code> → "
                     f"<code>{wanted}</code>\nСледующий заказ пройдёт — "
                     "попросите клиента повторить.")

        await delivery.notify_admins(
            bot,
            "⚠️ <b>Игровой заказ не прошёл</b>\n"
            f"├ Заказ: <code>{order.id}</code> — {game.title}\n"
            f"└ Клиенту вернули <b>{fmt(order.price)}</b>\n\n"
            f"<blockquote expandable>{str(exc)[:600]}</blockquote>{fixed}",
        )
        await call.message.answer(
            texts.REFUNDED.format(
                order_id=order.id, price=fmt(order.price), support=texts.support()
            ),
            reply_markup=keyboards.back(),
        )
        return
    except DeliveryUncertain as exc:
        # Ответа нет: деньги придерживаем, доглядчик разберётся сам.
        await db.transition_order(
            conn, order.id, expected=db.ORDER_DELIVERING, new=db.ORDER_FAILED,
            error=str(exc)[:1000],
        )
        await call.message.edit_text(
            texts.GAME_ACCEPTED.format(
                order_id=order.id, pack=data["pack"],
                player=data["player"], price=fmt(order.price),
            )
        )
        return

    await db.update_order(conn, order.id, fragment_order_id=external)
    await call.message.edit_text(
        texts.GAME_ACCEPTED.format(
            order_id=order.id, pack=data["pack"],
            player=data["player"], price=fmt(order.price),
        )
    )

    # Заказ почти всегда уходит в processing, поэтому проверяем сразу —
    # вдруг он уже готов, — а дальше за ним следит фоновая задача.
    fresh = await db.get_order(conn, order.id)
    if fresh:
        await svc.check(bot, conn, provider, fresh)

    await call.message.answer(
        "Меню:", reply_markup=await main_markup(conn)
    )
