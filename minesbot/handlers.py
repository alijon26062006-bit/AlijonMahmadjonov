"""Обработчики: команды, кнопки, текст. Здесь только «что ответить».

Деньги трогаются исключительно через db.* — то есть транзакциями. В этом файле
нет ни одной строчки вида «сначала списали, потом начислили».
"""

from __future__ import annotations

import asyncio
import html
import logging
from collections import defaultdict

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from . import db, keyboards, texts
from .config import CELLS, Config
from .game import Board, GameError, check_move, is_cleared, make_mines, multiplier, payout

log = logging.getLogger(__name__)

# Блокировка на игрока: пока обрабатывается одно его нажатие, второе ждёт.
# База и сама не даст сломать деньги, но так пользователь не видит гонок.
_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


def _cfg(context: ContextTypes.DEFAULT_TYPE) -> Config:
    return context.application.bot_data["config"]


def _conn(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data["conn"]


def _name(user) -> str:
    """Имя для показа — экранированное, иначе чужой ник сломает HTML-разметку."""

    return html.escape(user.full_name or user.username or str(user.id))[:64]


def _register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cfg = _cfg(context)
    user = update.effective_user
    return db.ensure_user(_conn(context), user.id, _name(user), cfg.start_balance)


async def _reply(update: Update, text: str, **kwargs):
    return await update.effective_message.reply_text(
        text, parse_mode=ParseMode.HTML, **kwargs
    )


# ── простые команды ────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    balance = _register(update, context)
    await _reply(update, texts.START + "\n\n" + texts.BALANCE.format(balance=texts.money(balance)))


async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    balance = _register(update, context)
    await _reply(update, texts.BALANCE.format(balance=texts.money(balance)))


async def bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = _cfg(context)
    _register(update, context)
    given, balance, minutes = db.claim_bonus(
        _conn(context), update.effective_user.id, cfg.bonus_amount, cfg.bonus_hours
    )
    if given:
        await _reply(update, texts.BONUS_OK.format(
            amount=texts.money(cfg.bonus_amount), balance=texts.money(balance)))
    else:
        await _reply(update, texts.BONUS_WAIT.format(
            minutes=minutes, balance=texts.money(balance)))


async def top(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _register(update, context)
    rows = db.top(_conn(context), 10)
    if not rows:
        await _reply(update, texts.TOP_EMPTY)
        return
    out = texts.TOP_HEAD
    for place, row in enumerate(rows, 1):
        out += texts.TOP_ROW.format(
            place=place,
            name=html.escape(row["name"] or str(row["user_id"])),
            balance=texts.money(int(row["balance"])),
        )
    await _reply(update, out)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    balance = _register(update, context)
    data = db.stats(_conn(context), update.effective_user.id)
    await _reply(update, texts.STATS.format(
        games=data["games"], won=data["won"], lost=data["lost"],
        net=texts.money(data["net"]) if data["net"] >= 0 else "−" + texts.money(-data["net"]),
        balance=texts.money(balance),
    ))


async def mines_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сколько мин класть в следующей игре. Настройка живёт у игрока."""

    cfg = _cfg(context)
    _register(update, context)
    if not context.args:
        await _reply(update, texts.NEED_NUMBER)
        return
    try:
        count = int(context.args[0])
    except ValueError:
        await _reply(update, texts.NEED_NUMBER)
        return
    if not 1 <= count <= CELLS - 1:
        await _reply(update, texts.MINES_RANGE)
        return
    context.user_data["mines"] = count
    await _reply(update, texts.MINES_SET.format(mines=count, bet=cfg.min_bet))


# ── игра ───────────────────────────────────────────────────────────────────

async def bet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/bet 100 — списать ставку и выложить поле."""

    cfg = _cfg(context)
    raw = context.args[0] if context.args else None
    await _start_game(update, context, raw, cfg)


async def _start_game(update: Update, context: ContextTypes.DEFAULT_TYPE, raw, cfg: Config) -> None:
    user_id = update.effective_user.id
    balance = _register(update, context)

    if raw is None:
        await _reply(update, texts.NEED_NUMBER)
        return
    # «1 000», «1_000», «100.» — приводим к числу, а не падаем.
    cleaned = str(raw).replace(" ", "").replace(" ", "").replace("_", "").rstrip(".")
    if cleaned.lower() in {"all", "hama", "ҳама"}:
        amount = min(balance, cfg.max_bet)
    else:
        try:
            amount = int(cleaned)
        except ValueError:
            await _reply(update, texts.NEED_NUMBER)
            return

    if not cfg.min_bet <= amount <= cfg.max_bet:
        await _reply(update, texts.BET_RANGE.format(
            low=texts.money(cfg.min_bet), high=texts.money(cfg.max_bet)))
        return
    if amount > balance:
        await _reply(update, texts.NOT_ENOUGH.format(balance=texts.money(balance)))
        return

    mines = int(context.user_data.get("mines", cfg.default_mines))

    async with _locks[user_id]:
        try:
            game = db.start_game(
                _conn(context), user_id, update.effective_chat.id,
                amount, mines, make_mines(mines),
            )
        except RuntimeError:
            await _reply(update, texts.ALREADY_PLAYING)
            return
        except db.Insufficient:
            await _reply(update, texts.NOT_ENOUGH.format(balance=texts.money(balance)))
            return

        board = Board(game.mine_cells, ())
        message = await _reply(
            update,
            keyboards.caption(amount, mines, 0, edge=cfg.house_edge),
            reply_markup=keyboards.field(game.game_id, board, amount, mines, edge=cfg.house_edge),
        )
        db.bind_message(_conn(context), game.game_id, message.message_id)


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Нажатие на клетку или на «Гирифтан».

    Каждое нажатие обязательно завершается answer(): иначе у игрока в клиенте
    вечно крутится «часики».
    """

    cfg = _cfg(context)
    query = update.callback_query
    parts = (query.data or "").split(":")
    if len(parts) != 4:
        await query.answer()
        return
    _, action, game_id, raw_index = parts

    if action == "x":  # пустышка на уже открытой клетке
        await query.answer()
        return

    user_id = query.from_user.id
    conn = _conn(context)

    async with _locks[user_id]:
        game = db.active_game(conn, user_id)
        # Чужая игра, старое сообщение после перезапуска, уже закрытая партия —
        # все три случая ловятся одной проверкой game_id.
        if game is None or game.game_id != game_id:
            row = conn.execute(
                "SELECT user_id FROM games WHERE game_id = ?", (game_id,)
            ).fetchone()
            if row is not None and int(row["user_id"]) != user_id:
                await query.answer(texts.NOT_YOUR_GAME, show_alert=True)
            else:
                await query.answer(texts.GAME_OVER, show_alert=True)
            await _disarm(query)
            return

        if action == "take":
            await _cashout(query, conn, cfg, game)
            return

        try:
            index = int(raw_index)
        except ValueError:
            await query.answer()
            return
        await _open(query, conn, cfg, game, index)


async def _disarm(query) -> None:
    """Снять кнопки у мёртвого сообщения, чтобы по нему больше не тыкали."""

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except BadRequest:
        pass


async def _cashout(query, conn, cfg: Config, game: db.Game) -> None:
    opened = len(game.opened)
    if opened == 0:
        await query.answer(texts.NOTHING_TO_TAKE, show_alert=True)
        return

    prize = payout(game.bet, opened, game.mines, edge=cfg.house_edge)
    try:
        balance = db.finish_game(conn, game.game_id, "cashout", prize)
    except db.NoGame:
        await query.answer(texts.GAME_OVER, show_alert=True)
        return

    await query.edit_message_text(
        texts.TAKEN.format(
            payout=texts.money(prize),
            multiplier=f"{multiplier(opened, game.mines, edge=cfg.house_edge):.2f}",
            bet=texts.money(game.bet),
            balance=texts.money(balance),
        ),
        parse_mode=ParseMode.HTML,
    )
    await query.answer()


async def _open(query, conn, cfg: Config, game: db.Game, index: int) -> None:
    board = Board(game.mine_cells, game.opened)
    try:
        hit_mine = check_move(index, board)
    except GameError:
        await query.answer(texts.CELL_TAKEN)
        return

    if hit_mine:
        # Мина: игру закрываем ДО отправки сообщения. Если Telegram не ответит,
        # партия всё равно уже завершена и повторно сыграть её нельзя.
        try:
            db.open_cell(conn, game.game_id, index)
            balance = db.finish_game(conn, game.game_id, "lost", 0)
        except db.NoGame:
            await query.answer(texts.GAME_OVER, show_alert=True)
            return
        opened = len(game.opened)
        await query.edit_message_text(
            texts.BOOM.format(
                bet=game.bet,
                stake=texts.money(game.bet),
                opened=opened,
                multiplier=f"{multiplier(opened, game.mines, edge=cfg.house_edge):.2f}",
                balance=texts.money(balance),
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=keyboards.field(
                game.game_id,
                Board(game.mine_cells, game.opened + (index,), revealed=True),
                game.bet, game.mines, edge=cfg.house_edge, dead=True,
            ),
        )
        await query.answer("💥 БУМ!")
        return

    try:
        game = db.open_cell(conn, game.game_id, index)
    except db.NoGame:
        await query.answer(texts.CELL_TAKEN)
        return

    opened = len(game.opened)
    board = Board(game.mine_cells, game.opened)
    prize = payout(game.bet, opened, game.mines, edge=cfg.house_edge)

    if is_cleared(board):
        # Открыты все безопасные клетки — дальше жать некуда, платим сами.
        balance = db.finish_game(conn, game.game_id, "cleared", prize)
        await query.edit_message_text(
            texts.CLEARED.format(
                payout=texts.money(prize),
                multiplier=f"{multiplier(opened, game.mines, edge=cfg.house_edge):.2f}",
                balance=texts.money(balance),
            ),
            parse_mode=ParseMode.HTML,
        )
        await query.answer()
        return

    await query.edit_message_text(
        keyboards.caption(game.bet, game.mines, opened, edge=cfg.house_edge),
        parse_mode=ParseMode.HTML,
        reply_markup=keyboards.field(game.game_id, board, game.bet, game.mines, edge=cfg.house_edge),
    )
    await query.answer(texts.CELL_WIN.format(
        multiplier=f"{multiplier(opened, game.mines, edge=cfg.house_edge):.2f}",
        payout=texts.money(prize),
    ))


# ── переводы между игроками ────────────────────────────────────────────────

async def send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/send 100 в ответ на сообщение — перевести монеты."""

    cfg = _cfg(context)
    message = update.effective_message
    sender = update.effective_user
    balance = _register(update, context)

    target = message.reply_to_message.from_user if message.reply_to_message else None
    if target is None or not context.args:
        await _reply(update, texts.SEND_HOW)
        return
    if target.is_bot:
        await _reply(update, texts.SEND_TO_BOT)
        return
    if target.id == sender.id:
        await _reply(update, texts.SEND_TO_SELF)
        return

    try:
        amount = int(str(context.args[0]).replace(" ", "").replace("_", ""))
    except ValueError:
        await _reply(update, texts.NEED_NUMBER)
        return
    if amount <= 0 or amount > balance:
        await _reply(update, texts.NOT_ENOUGH.format(balance=texts.money(balance)))
        return

    conn = _conn(context)
    # Получателя надо завести ДО перевода: иначе деньги уйдут в никуда.
    db.ensure_user(conn, target.id, _name(target), cfg.start_balance)

    async with _locks[sender.id]:
        try:
            left, got = db.transfer(conn, sender.id, target.id, amount)
        except db.Insufficient:
            await _reply(update, texts.NOT_ENOUGH.format(
                balance=texts.money(db.balance(conn, sender.id))))
            return

    await _reply(update, texts.SEND_OK.format(
        amount=texts.money(amount), name=_name(target), balance=texts.money(left)))
    try:
        await context.bot.send_message(
            target.id,
            texts.SEND_GOT.format(
                name=_name(sender), amount=texts.money(amount), balance=texts.money(got)),
            parse_mode=ParseMode.HTML,
        )
    except Exception:  # получатель не писал боту — это не ошибка перевода
        log.info("не смог уведомить получателя %s", target.id)


# ── свободный текст ────────────────────────────────────────────────────────

async def text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Просто число в чате = ставка. Слово «баланс» = баланс."""

    body = (update.effective_message.text or "").strip()
    low = body.lower()

    if low in {"баланс", "balans", "💳"}:
        await balance_cmd(update, context)
        return
    if low in {"бонус", "bonus", "🎁"}:
        await bonus(update, context)
        return
    if low in {"топ", "top", "🏆"}:
        await top(update, context)
        return

    digits = body.replace(" ", "").replace(" ", "").replace("_", "")
    if digits.isdigit():
        await _start_game(update, context, digits, _cfg(context))
        return

    # В группе не отвечаем на каждое слово — только в личке.
    if update.effective_chat.type == "private":
        await _reply(update, texts.HELP)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Любая необработанная ошибка: пишем в лог и говорим человеку по-человечески."""

    log.exception("необработанная ошибка", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(texts.ERROR)
        except Exception:
            pass
