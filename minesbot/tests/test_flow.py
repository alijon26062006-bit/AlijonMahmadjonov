"""Сквозные проверки: ставка → клетки → забрать, и все злые случаи."""

from minesbot import db, handlers
from minesbot.tests.conftest import (
    FakeBot, FakeContext, FakeMessage, FakeQuery, FakeUpdate, FakeUser,
)

ALI = FakeUser(1, "Ali")
BEK = FakeUser(2, "Bek")


def _update(text="", user=ALI, reply_to=None):
    message = FakeMessage(text, user=user, reply_to=reply_to)
    return FakeUpdate(message, user)


async def _bet(app, amount=100, user=ALI, mines=None):
    update = _update(f"/bet {amount}", user)
    context = FakeContext(app, args=[str(amount)], user_data={"mines": mines} if mines else {})
    await handlers.bet(update, context)
    return update, context


def _game(conn, user=ALI):
    return db.active_game(conn, user.id)


def _cell(game, mine: bool):
    """Индекс клетки: с миной или без."""

    if mine:
        return game.mine_cells[0]
    return next(i for i in range(25) if i not in game.mine_cells and i not in game.opened)


async def test_start_registers_and_shows_balance(app):
    update = _update("/start")
    await handlers.start(update, FakeContext(app))
    assert "1 000" in update.effective_message.sent[0].text.replace(" ", " ")


async def test_bet_charges_and_draws_field(app, conn):
    update, _ = await _bet(app)
    assert db.balance(conn, ALI.id) == 900
    board = update.effective_message.sent[0].markup.inline_keyboard
    assert len(board) == 6                      # 5 рядов поля + «Гирифтан»
    assert _game(conn).bet == 100


async def test_bet_too_small_is_refused(app, conn):
    update = _update("/bet 1")
    await handlers.bet(update, FakeContext(app, args=["1"]))
    assert "Сатҳ аз" in update.effective_message.sent[0].text
    assert db.balance(conn, ALI.id) == 1000


async def test_bet_over_balance_is_refused(app, conn):
    update = _update("/bet 99999")
    await handlers.bet(update, FakeContext(app, args=["99999"]))
    assert "кофӣ нест" in update.effective_message.sent[0].text
    assert db.balance(conn, ALI.id) == 1000


async def test_second_game_is_refused(app, conn):
    await _bet(app)
    update, _ = await _bet(app)
    assert "аллакай бозӣ дорӣ" in update.effective_message.sent[0].text
    assert db.balance(conn, ALI.id) == 900      # вторая ставка не списана


async def test_safe_cell_raises_multiplier(app, conn):
    await _bet(app)
    game = _game(conn)
    query = FakeQuery(f"mn:o:{game.game_id}:{_cell(game, mine=False)}", ALI, None)
    await handlers.buttons(_query_update(query), FakeContext(app))
    assert "x1.10" in query.answers[0][0]
    assert len(_game(conn).opened) == 1


async def test_same_cell_twice_counts_once(app, conn):
    await _bet(app)
    game = _game(conn)
    index = _cell(game, mine=False)
    for _ in range(2):
        query = FakeQuery(f"mn:o:{game.game_id}:{index}", ALI, None)
        await handlers.buttons(_query_update(query), FakeContext(app))
    assert _game(conn).opened == (index,)


async def test_cashout_pays_once(app, conn):
    await _bet(app)
    game = _game(conn)
    query = FakeQuery(f"mn:o:{game.game_id}:{_cell(game, mine=False)}", ALI, None)
    await handlers.buttons(_query_update(query), FakeContext(app))

    take = FakeQuery(f"mn:take:{game.game_id}:0", ALI, None)
    await handlers.buttons(_query_update(take), FakeContext(app))
    assert db.balance(conn, ALI.id) == 1010     # 900 + 110

    again = FakeQuery(f"mn:take:{game.game_id}:0", ALI, None)
    await handlers.buttons(_query_update(again), FakeContext(app))
    assert db.balance(conn, ALI.id) == 1010     # второй раз не платим
    assert again.answers[0][0] == "❌ Бозӣ тамом шудааст."


async def test_cashout_without_open_cells_is_refused(app, conn):
    await _bet(app)
    game = _game(conn)
    take = FakeQuery(f"mn:take:{game.game_id}:0", ALI, None)
    await handlers.buttons(_query_update(take), FakeContext(app))
    assert "бурд надорӣ" in take.answers[0][0]
    assert db.balance(conn, ALI.id) == 900
    assert _game(conn) is not None              # игра продолжается


async def test_mine_ends_game_and_shows_field(app, conn):
    await _bet(app)
    game = _game(conn)
    query = FakeQuery(f"mn:o:{game.game_id}:{_cell(game, mine=True)}", ALI, None)
    await handlers.buttons(_query_update(query), FakeContext(app))
    assert "МИНА" in query.edits[0]
    assert db.balance(conn, ALI.id) == 900      # ставка уже была списана
    assert _game(conn) is None
    # после взрыва все кнопки обезврежены
    assert all(b.callback_data == "mn:x:0:0" for row in query.markups[0].inline_keyboard for b in row)


async def test_foreign_user_cannot_press(app, conn):
    await _bet(app)
    game = _game(conn)
    db.ensure_user(conn, BEK.id, "Bek", 1000)
    query = FakeQuery(f"mn:o:{game.game_id}:{_cell(game, mine=False)}", BEK, None)
    await handlers.buttons(_query_update(query), FakeContext(app))
    assert query.answers[0] == ("❌ Ин бозии ту нест!", True)
    assert _game(conn).opened == ()


async def test_stale_button_from_old_message(app, conn):
    """Кнопка старой (уже закрытой) партии не трогает новую."""

    await _bet(app)
    old = _game(conn)
    db.finish_game(conn, old.game_id, "cashout", 0)
    await _bet(app, 200)
    new = _game(conn)

    query = FakeQuery(f"mn:o:{old.game_id}:0", ALI, None)
    await handlers.buttons(_query_update(query), FakeContext(app))
    assert query.answers[0] == ("❌ Бозӣ тамом шудааст.", True)
    assert _game(conn).game_id == new.game_id and _game(conn).opened == ()


async def test_broken_callback_data_is_ignored(app):
    query = FakeQuery("mn:garbage", ALI, None)
    await handlers.buttons(_query_update(query), FakeContext(app))
    assert query.answers == [(None, False)]


async def test_clearing_whole_field_pays_out(app, conn):
    await _bet(app, 100, mines=24)              # 24 мины: безопасная клетка одна
    game = _game(conn)
    safe = _cell(game, mine=False)
    query = FakeQuery(f"mn:o:{game.game_id}:{safe}", ALI, None)
    await handlers.buttons(_query_update(query), FakeContext(app))
    assert "🏆" in query.edits[0]
    assert db.balance(conn, ALI.id) == 900 + 2425
    assert _game(conn) is None


async def test_send_moves_money_between_players(app, conn):
    bot = FakeBot()
    target_message = FakeMessage("салом", user=BEK)
    update = _update("/send 300", reply_to=target_message)
    await handlers.send(update, FakeContext(app, args=["300"], bot=bot))
    assert db.balance(conn, ALI.id) == 700
    assert db.balance(conn, BEK.id) == 1300
    assert bot.messages and bot.messages[0][0] == BEK.id


async def test_send_more_than_balance_is_refused(app, conn):
    update = _update("/send 5000", reply_to=FakeMessage("салом", user=BEK))
    await handlers.send(update, FakeContext(app, args=["5000"]))
    assert "кофӣ нест" in update.effective_message.sent[0].text
    assert db.balance(conn, ALI.id) == 1000


async def test_send_to_self_and_to_bot_is_refused(app, conn):
    me = _update("/send 10", reply_to=FakeMessage("я", user=ALI))
    await handlers.send(me, FakeContext(app, args=["10"]))
    assert "худат" in me.effective_message.sent[0].text

    bot_user = FakeUser(99, "Bot", is_bot=True)
    to_bot = _update("/send 10", reply_to=FakeMessage("бот", user=bot_user))
    await handlers.send(to_bot, FakeContext(app, args=["10"]))
    assert "бот" in to_bot.effective_message.sent[0].text.lower()
    assert db.balance(conn, ALI.id) == 1000


async def test_bonus_cooldown(app, conn):
    update = _update("/bonus")
    await handlers.bonus(update, FakeContext(app))
    assert db.balance(conn, ALI.id) == 1500
    await handlers.bonus(update, FakeContext(app))
    assert db.balance(conn, ALI.id) == 1500
    assert "дақиқа" in update.effective_message.sent[1].text


async def test_plain_number_starts_game(app, conn):
    update = _update("250")
    await handlers.text(update, FakeContext(app))
    assert db.balance(conn, ALI.id) == 750
    assert _game(conn).bet == 250


async def test_mines_command_changes_next_game(app, conn):
    context = FakeContext(app, args=["10"])
    await handlers.mines_cmd(_update("/mines 10"), context)
    assert context.user_data["mines"] == 10
    update = _update("/bet 100")
    context.args = ["100"]
    await handlers.bet(update, context)
    assert _game(conn).mines == 10


async def test_mines_out_of_range(app):
    update = _update("/mines 99")
    await handlers.mines_cmd(update, FakeContext(app, args=["99"]))
    assert "1 то 24" in update.effective_message.sent[0].text


def _query_update(query):
    """Update, у которого есть только callback_query."""

    class _U:
        callback_query = query
    return _U()
