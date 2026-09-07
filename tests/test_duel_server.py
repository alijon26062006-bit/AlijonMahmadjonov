"""Сквозной тест: два игрока подключаются по WebSocket и играют матч."""

import asyncio
import time
from pathlib import Path

import pytest
from aiohttp import WSMsgType
from aiohttp.test_utils import TestClient, TestServer

from duel import game, robot as robot_mod, storage
from duel.config import DuelConfig
from duel.server import Hub, make_app
from tests.test_duel_auth import TOKEN, make_init_data


class Player:
    """Игрок в тесте: читает сокет в фоне, чтобы ожидание не рвало связь."""

    def __init__(self, ws):
        self.ws = ws
        self.inbox: asyncio.Queue = asyncio.Queue()
        self.pending: list = []
        self._pump = asyncio.create_task(self._read())

    async def _read(self):
        async for message in self.ws:
            if message.type is WSMsgType.TEXT:
                await self.inbox.put(message.json())

    async def send(self, **payload):
        await self.ws.send_json(payload)

    async def recv(self, kind, timeout=6.0):
        """Ждёт сообщение нужного вида. Остальные откладывает, а не теряет."""

        for index, message in enumerate(self.pending):
            if message.get("t") == kind:
                return self.pending.pop(index)

        async def wait():
            while True:
                message = await self.inbox.get()
                if message.get("t") == kind:
                    return message
                self.pending.append(message)

        return await asyncio.wait_for(wait(), timeout)

    async def silent(self, kind, timeout=0.6):
        """Проверяет, что такого сообщения не приходит."""
        with pytest.raises(asyncio.TimeoutError):
            await self.recv(kind, timeout)

    async def close(self):
        self._pump.cancel()
        await self.ws.close()


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setattr(game, "COUNTDOWN_SEC", 0.05)
    config = DuelConfig(
        bot_token=TOKEN,
        public_url="https://duel.example.com",
        data_dir=Path(tmp_path),
        tick_hz=50,
    )
    conn = storage.connect(config.db_path)
    posted: list = []

    async def notify(user_id, text, button=None, url=None):
        posted.append({"to": user_id, "text": text, "button": button, "url": url})

    hub = Hub(config, conn, notify=notify, bot_username="duel_bot")
    test_client = TestClient(TestServer(make_app(hub)))
    test_client.posted = posted
    await test_client.start_server()
    test_client.hub = hub
    test_client.players = []
    yield test_client
    for player in test_client.players:
        player._pump.cancel()
    await test_client.close()
    conn.close()


async def join(client, user_id, name="Игрок"):
    player = Player(await client.ws_connect("/ws"))
    client.players.append(player)
    await player.send(t="hello", initData=make_init_data(user_id=user_id, name=name))
    return player, await player.recv("ready")


async def play(client, duration=30, level="normal"):
    """Заводит двоих в один матч и возвращает их вместе с первыми примерами."""
    one, _ = await join(client, 1, "Первый")
    two, _ = await join(client, 2, "Второй")
    for player in (one, two):
        await player.send(t="find", duration=duration, level=level)
    await one.recv("found")
    await two.recv("found")
    return one, two, await one.recv("task"), await two.recv("task")


async def respond(player, hub, user_id, task_id, correct=True):
    """Отвечает как живой человек: не мгновенно, иначе сервер решит, что это бот."""
    await asyncio.sleep(game.MIN_SOLVE_SEC + 0.03)
    match = hub.match_for(user_id)
    value = match.side(user_id).task.answer + (0 if correct else 7)
    await player.send(t="answer", id=task_id, v=value, ms=900)


async def state_where(player, check, tries=40):
    """Ждёт состояние, которое удовлетворяет условию."""
    for _ in range(tries):
        message = await player.recv("state")
        if check(message):
            return message
    raise AssertionError("подходящее состояние не пришло")


# ── вход ────────────────────────────────────────────────────────────


async def test_valid_player_gets_in(client):
    _, ready = await join(client, 1, "Алиджон")
    assert ready["profile"]["name"] == "Алиджон"
    assert ready["profile"]["rating"] == 1000
    assert ready["strings"]["play"]


async def test_forged_init_data_is_refused(client):
    player = Player(await client.ws_connect("/ws"))
    client.players.append(player)
    await player.send(t="hello", initData="user=%7B%22id%22%3A1%7D&hash=00")
    assert (await player.recv("error"))["code"] == "auth"


async def test_nothing_works_before_hello(client):
    player = Player(await client.ws_connect("/ws"))
    client.players.append(player)
    await player.send(t="find", duration=30, level="normal")
    assert (await player.recv("error"))["code"] == "no_hello"


async def test_language_choice_is_saved(client):
    player, ready = await join(client, 1)
    assert ready["lang"] == "ru"
    await player.send(t="lang", lang="tg")
    assert (await player.recv("strings"))["strings"]["play"] == "Рақиб ёфтан"
    await player.close()
    _, again = await join(client, 1)
    assert again["lang"] == "tg"


# ── подбор соперника ────────────────────────────────────────────────


async def test_two_players_find_each_other(client):
    _, _, task_one, task_two = await play(client)
    assert task_one["q"] and task_two["q"]
    assert "answer" not in task_one, "правильный ответ клиенту не уходит"


async def test_a_single_player_just_waits(client):
    player, _ = await join(client, 1)
    await player.send(t="find", duration=30, level="normal")
    await player.recv("queued")
    await player.silent("found")


# ── когда живых нет ─────────────────────────────────────────────────────────


async def test_after_half_a_minute_alone_the_game_offers_a_robot(client):
    player, _ = await join(client, 1)
    await player.send(t="find", duration=30, level="normal")
    await player.recv("queued")
    await player.silent("offer_bot", timeout=0.5)

    # Перематываем ожидание: сидеть в тесте полминуты незачем.
    client.hub.queue.tickets[1].joined_at -= 31
    offer = await player.recv("offer_bot", timeout=4)
    assert offer["online"] == 1 and offer["waited"] >= 30


async def test_the_offer_comes_once_and_not_again(client):
    player, _ = await join(client, 1)
    await player.send(t="find", duration=30, level="normal")
    await player.recv("queued")
    client.hub.queue.tickets[1].joined_at -= 31
    await player.recv("offer_bot", timeout=4)
    await player.silent("offer_bot", timeout=1.5)


async def test_a_new_search_may_be_offered_a_robot_again(client):
    player, _ = await join(client, 1)
    await player.send(t="find", duration=30, level="normal")
    await player.recv("queued")
    client.hub.queue.tickets[1].joined_at -= 31
    await player.recv("offer_bot", timeout=4)

    await player.send(t="cancel")
    await player.recv("idle")
    await player.send(t="find", duration=30, level="normal")
    await player.recv("queued")
    client.hub.queue.tickets[1].joined_at -= 31
    assert await player.recv("offer_bot", timeout=4)


async def test_playing_against_the_robot(client, monkeypatch):
    """Робот должен и правда отвечать, а не стоять столбом."""
    monkeypatch.setattr(robot_mod, "MIN_THINK", 0.25)
    monkeypatch.setattr(robot_mod, "SPEEDS", {"normal": (0.3, 0.0), "slow": (0.3, 0.0),
                                              "fast": (0.3, 0.0)})
    player, _ = await join(client, 1, "Алиджон")
    await player.send(t="play_bot", duration=0, level="easy")

    found = await player.recv("found")
    assert found["opp"]["name"] == "Робот"
    await player.recv("task")

    state = await player.recv("state", timeout=6)
    while state["opp"]["score"] == 0:
        state = await player.recv("state", timeout=6)
    assert state["rope"] < 0, "робот тянет канат на себя"


async def test_training_does_not_touch_the_rating(client, monkeypatch):
    monkeypatch.setattr(robot_mod, "MIN_THINK", 0.25)
    monkeypatch.setattr(robot_mod, "SPEEDS", {"fast": (0.3, 0.0), "normal": (0.3, 0.0),
                                              "slow": (0.3, 0.0)})
    player, _ = await join(client, 1, "Алиджон")
    await player.send(t="play_bot", duration=0, level="easy")
    await player.recv("found")

    result = await player.recv("end", timeout=30)
    assert result["rated"] is False and result["delta"] == 0
    row = storage.get_player(client.hub.db, 1)
    assert row["games"] == 0 and row["rating"] == 1000
    assert storage.totals(client.hub.db)["matches"] == 0, "тренировка не идёт в историю"


async def test_the_robot_is_not_counted_among_people_online(client):
    player, _ = await join(client, 1)
    await player.send(t="play_bot", duration=30, level="easy")
    await player.recv("found")
    assert client.hub.online_stats()["online"] == 1


async def test_leaving_the_queue_returns_to_the_menu(client):
    player, _ = await join(client, 1)
    await player.send(t="find", duration=30, level="normal")
    await player.recv("queued")
    await player.send(t="cancel")
    await player.recv("idle")
    assert len(client.hub.queue) == 0


async def test_friend_room_pairs_by_code(client):
    one, _ = await join(client, 1)
    two, _ = await join(client, 2)
    await one.send(t="room", duration=30, level="easy")
    room = await one.recv("room")
    assert "duel_bot" in room["link"]
    await two.send(t="join", code=room["code"], duration=30, level="easy")
    assert (await one.recv("found"))["opp"]
    assert (await two.recv("found"))["opp"]


async def test_invite_shows_who_is_calling_before_the_fight(client):
    """Гость должен увидеть, кто зовёт, и нажать кнопку сам: влетать в бой
    врасплох — верный способ проиграть первые секунды."""
    one, _ = await join(client, 1, "Алиджон")
    two, _ = await join(client, 2, "Гость")
    await one.send(t="room", duration=30, level="easy")
    room = await one.recv("room")

    await two.send(t="peek", code=room["code"])
    invite = await two.recv("invite")
    assert invite["host"]["name"] == "Алиджон"
    assert invite["host"]["rating"] == 1000
    assert invite["duration"] == 30 and invite["level"] == "easy"
    assert invite["code"] == room["code"]

    # Заглянуть — не значит войти: комната всё ещё ждёт.
    assert client.hub.queue.find_room(room["code"]) is not None
    await two.silent("found", timeout=0.5)

    await two.send(t="join", code=room["code"], duration=30, level="easy")
    assert (await one.recv("found"))["opp"]["name"] == "Гость"


async def test_peek_at_a_room_that_is_gone(client):
    player, _ = await join(client, 1)
    await player.send(t="peek", code="НЕТУ")
    await player.recv("room_error")


async def test_you_cannot_invite_yourself(client):
    one, _ = await join(client, 1)
    await one.send(t="room", duration=30, level="easy")
    room = await one.recv("room")
    await one.send(t="peek", code=room["code"])
    await one.recv("room_error")


# ── список игроков и личный вызов ───────────────────────────────────────────


async def test_player_list_puts_those_online_on_top(client):
    """Смысл списка в том, чтобы сверху были те, с кем можно сыграть сейчас."""
    storage.touch_player(client.hub.db, 7, "Давний")
    client.hub.db.execute(
        "UPDATE players SET last_seen_at = '2024-01-01T00:00:00+00:00' WHERE id = 7"
    )
    client.hub.db.commit()
    await join(client, 2, "Соперник")
    one, _ = await join(client, 1, "Алиджон")

    await one.send(t="players")
    people = (await one.recv("players"))["list"]
    names = [p["name"] for p in people]
    assert "Алиджон" not in names, "себя в списке быть не должно"
    assert names[0] == "Соперник" and people[0]["online"] is True
    assert names[-1] == "Давний"
    assert people[-1]["seen"] > 30 * 24 * 3600, "давний вход виден по времени"


async def test_calling_someone_reaches_them_on_screen_and_in_chat(client):
    two, _ = await join(client, 2, "Соперник")
    one, _ = await join(client, 1, "Алиджон")

    await one.send(t="challenge", to=2, duration=30, level="easy")
    sent = await one.recv("challenge_sent")
    assert sent["to"]["name"] == "Соперник" and sent["to"]["online"] is True

    invite = await two.recv("invite")
    assert invite["host"]["name"] == "Алиджон"
    assert invite["code"] == sent["code"]

    letter = client.posted[-1]
    assert letter["to"] == 2
    assert "Алиджон" in letter["text"]
    assert sent["code"] in letter["url"], "кнопка в чате должна вести в тот же бой"

    await two.send(t="join", code=sent["code"], duration=30, level="easy")
    assert (await one.recv("found"))["opp"]["name"] == "Соперник"


async def test_call_reaches_the_chat_even_when_the_game_is_closed(client):
    storage.touch_player(client.hub.db, 5, "Ушедший")
    one, _ = await join(client, 1, "Алиджон")
    await one.send(t="challenge", to=5, duration=30, level="easy")
    sent = await one.recv("challenge_sent")
    assert sent["to"]["online"] is False
    assert client.posted[-1]["to"] == 5


async def test_a_personal_call_is_not_for_strangers(client):
    two, _ = await join(client, 2, "Соперник")
    three, _ = await join(client, 3, "Посторонний")
    one, _ = await join(client, 1, "Алиджон")
    await one.send(t="challenge", to=2, duration=30, level="easy")
    sent = await one.recv("challenge_sent")

    await three.send(t="join", code=sent["code"], duration=30, level="easy")
    await three.recv("room_error")
    assert client.hub.queue.find_room(sent["code"]) is not None, "комната ждёт своего"


async def test_you_cannot_call_the_same_person_over_and_over(client):
    await join(client, 2, "Соперник")
    one, _ = await join(client, 1, "Алиджон")

    await one.send(t="challenge", to=2)
    await one.recv("challenge_sent")

    await one.send(t="challenge", to=2)
    assert (await one.recv("challenge_error"))["reason"] == "too_often"

    # Даже когда общий перерыв прошёл, одному и тому же — не чаще раза в минуту.
    client.hub._called_at.clear()
    await one.send(t="challenge", to=2)
    assert (await one.recv("challenge_error"))["reason"] == "already"


async def test_calling_a_ghost_says_so(client):
    one, _ = await join(client, 1)
    await one.send(t="challenge", to=99999)
    assert (await one.recv("challenge_error"))["reason"] == "gone"


async def test_invite_link_opens_the_game_in_one_tap_when_set_up(client):
    """С настроенным главным мини-приложением ссылка открывает игру сразу —
    даже у того, кто бота ни разу не запускал."""
    client.hub.main_app = True
    one, _ = await join(client, 1)
    await one.send(t="room", duration=30, level="easy")
    room = await one.recv("room")
    assert room["link"] == f"https://t.me/duel_bot?startapp={room['code']}"


async def test_without_the_main_mini_app_the_link_goes_through_the_chat(client):
    """Без настройки ?startapp= откроет переписку, а не игру, — тогда ссылка
    должна быть такой, на которую бот сможет ответить кнопкой."""
    client.hub.main_app = False
    one, _ = await join(client, 1)
    await one.send(t="room", duration=30, level="easy")
    room = await one.recv("room")
    assert room["link"] == f"https://t.me/duel_bot?start={room['code']}"


async def test_the_same_link_goes_into_the_chat_invitation(client):
    client.hub.main_app = True
    await join(client, 2, "Соперник")
    one, _ = await join(client, 1, "Алиджон")
    await one.send(t="challenge", to=2)
    sent = await one.recv("challenge_sent")
    assert f"startapp={sent['code']}" in client.posted[-1]["text"]


async def test_without_a_bot_name_there_is_no_link(client):
    client.hub.bot_username = ""
    assert client.hub.invite_link("ABC123") == ""


async def test_sharing_a_link_does_not_kill_the_room(client):
    """Кнопка «Отправить другу» уводит из игры — Telegram открывает выбор чата.
    Если комната умирает вместе с окном, ссылка у друга оказывается мёртвой."""
    host, _ = await join(client, 1, "Алиджон")
    await host.send(t="room", duration=30, level="easy")
    room = await host.recv("room")

    await host.close()
    await asyncio.sleep(0.3)
    assert client.hub.queue.find_room(room["code"]) is not None


async def test_friend_accepts_while_the_host_is_away(client):
    host, _ = await join(client, 1, "Алиджон")
    await host.send(t="room", duration=30, level="easy")
    room = await host.recv("room")
    await host.close()
    await asyncio.sleep(0.3)

    guest, _ = await join(client, 2, "Друг")
    await guest.send(t="join", code=room["code"], duration=30, level="easy")
    waiting = await guest.recv("waiting_host")
    assert waiting["name"] == "Алиджон"

    # Хозяина позвали обратно письмом в чат.
    letter = client.posted[-1]
    assert letter["to"] == 1 and "Друг" in letter["text"]

    # Он вернулся — бой начинается сам, без лишних нажатий.
    again, _ = await join(client, 1, "Алиджон")
    assert (await again.recv("found"))["opp"]["name"] == "Друг"
    assert (await guest.recv("found"))["opp"]["name"] == "Алиджон"


async def test_the_guest_is_let_go_if_the_host_never_returns(client, monkeypatch):
    monkeypatch.setattr("duel.server.HOST_GRACE_SEC", 0.2)
    host, _ = await join(client, 1, "Алиджон")
    await host.send(t="room", duration=30, level="easy")
    room = await host.recv("room")
    await host.close()
    await asyncio.sleep(0.3)

    guest, _ = await join(client, 2, "Друг")
    await guest.send(t="join", code=room["code"], duration=30, level="easy")
    await guest.recv("waiting_host")
    assert (await guest.recv("host_gone", timeout=4))["name"] == "Алиджон"
    assert client.hub.queue.find_room(room["code"]) is None


async def test_leaving_on_purpose_still_closes_the_room(client):
    """Нажал «Отмена» — это уже не отлучка, комнаты быть не должно."""
    host, _ = await join(client, 1, "Алиджон")
    await host.send(t="room", duration=30, level="easy")
    room = await host.recv("room")
    await host.send(t="cancel")
    await host.recv("idle")
    assert client.hub.queue.find_room(room["code"]) is None


async def test_wrong_room_code_says_so(client):
    player, _ = await join(client, 1)
    await player.send(t="join", code="НЕТУ", duration=30, level="easy")
    await player.recv("room_error")


# ── ход матча ───────────────────────────────────────────────────────


async def test_correct_answer_pulls_the_rope(client):
    one, two, task, _ = await play(client)
    await respond(one, client.hub, 1, task["id"])
    assert (await one.recv("ans"))["correct"] is True
    assert (await one.recv("task"))["id"] != task["id"], "сразу приходит новый пример"

    mine = await state_where(one, lambda m: m["me"]["score"] == 1)
    assert mine["rope"] == 1
    theirs = await state_where(two, lambda m: m["opp"]["score"] == 1)
    assert theirs["rope"] == -1, "соперник видит канат со своей стороны"


async def test_wrong_answer_freezes_the_keypad(client):
    one, _, task, _ = await play(client)
    await respond(one, client.hub, 1, task["id"], correct=False)
    reply = await one.recv("ans")
    assert reply["correct"] is False
    assert reply["freeze_ms"] >= 1000
    assert client.hub.match_for(1).rope() == 0


async def test_instant_answers_are_treated_as_a_robot(client):
    """Быстрее, чем человек успевает нажать, — значит, отвечает скрипт."""
    one, _, task, _ = await play(client)
    match = client.hub.match_for(1)
    await one.send(t="answer", id=task["id"], v=match.side(1).task.answer)
    assert (await one.recv("ans"))["correct"] is False
    assert client.hub.match_for(1).rope() == 0


async def test_answer_to_an_old_task_is_ignored(client):
    one, _, task, _ = await play(client)
    await respond(one, client.hub, 1, task["id"])
    await one.recv("ans")
    await one.send(t="answer", id=task["id"], v=0)
    await one.silent("ans")


async def test_pulling_the_rope_to_the_edge_wins_the_match(client):
    one, two, task, _ = await play(client, duration=0)
    current = task["id"]
    for _ in range(game.WIN_STEPS + 4):
        if client.hub.match_for(1) is None:
            break
        await respond(one, client.hub, 1, current)
        if not (await one.recv("ans"))["correct"]:
            break
        try:
            current = (await one.recv("task", timeout=0.5))["id"]
        except asyncio.TimeoutError:
            break

    win = await one.recv("end")
    loss = await two.recv("end")
    assert win["outcome"] == "win" and win["reason"] == "rope"
    assert loss["outcome"] == "loss"
    assert win["delta"] > 0 > loss["delta"]
    assert win["rating"] > 1000 > loss["rating"]
    assert win["best_streak"] >= 3


async def test_time_running_out_ends_the_match(client):
    one, two, task, _ = await play(client)
    await respond(one, client.hub, 1, task["id"])
    await one.recv("ans")
    # Не ждём полминуты: сдвигаем финиш матча к текущему моменту.
    client.hub.match_for(1).deadline = time.monotonic() + 0.2
    result = await one.recv("end")
    assert result["reason"] == "time" and result["outcome"] == "win"
    assert (await two.recv("end"))["outcome"] == "loss"


async def test_an_untouched_match_does_not_change_ratings(client):
    one, two, _, _ = await play(client)
    client.hub.match_for(1).deadline = time.monotonic() + 0.2
    result = await one.recv("end")
    assert result["rated"] is False and result["delta"] == 0
    assert storage.get_player(client.hub.db, 1)["games"] == 0


async def test_leaving_hands_the_win_to_the_opponent(client):
    one, two, _, _ = await play(client)
    await one.send(t="leave")
    assert (await two.recv("end"))["outcome"] == "win"


async def test_a_dropped_connection_is_not_an_instant_loss(client):
    one, two, _, _ = await play(client)
    await one.close()
    await two.recv("opp_offline")
    await two.silent("end", timeout=0.8)
    assert client.hub.match_for(2) is not None


async def test_coming_back_returns_the_player_to_the_field(client):
    one, two, _, _ = await play(client)
    match_id = client.hub.match_for(1).id
    await one.close()
    await two.recv("opp_offline")

    again, _ = await join(client, 1)
    assert (await again.recv("found"))["match"] == match_id
    assert await again.recv("task"), "пример выдаётся заново"
    assert await again.recv("state")


async def test_opening_the_app_twice_closes_the_first_window(client):
    first, _ = await join(client, 1)
    second, _ = await join(client, 1)
    assert (await first.recv("error"))["code"] == "replaced"


# ── итоги ───────────────────────────────────────────────────────────


async def test_the_match_lands_in_the_database(client):
    one, two, task, _ = await play(client)
    await respond(one, client.hub, 1, task["id"])
    await one.recv("ans")
    client.hub.match_for(1).deadline = time.monotonic() + 0.2
    await one.recv("end")

    assert storage.totals(client.hub.db)["matches"] == 1
    row = storage.get_player(client.hub.db, 1)
    assert row["games"] == 1 and row["wins"] == 1 and row["correct"] >= 1
    assert len(storage.history(client.hub.db, 2)) == 1


async def test_leaderboard_is_public(client):
    one, two, task, _ = await play(client)
    await respond(one, client.hub, 1, task["id"])
    await one.recv("ans")
    client.hub.match_for(1).deadline = time.monotonic() + 0.2
    await one.recv("end")
    await two.recv("end")

    data = await (await client.get("/api/top")).json()
    assert [row["place"] for row in data["top"]] == [1, 2]
    assert data["top"][0]["rating"] > data["top"][1]["rating"]


async def test_online_counter_comes_with_the_first_message(client):
    _, ready = await join(client, 1)
    assert ready["online"] == 1
    assert ready["searching"] == 0 and ready["playing"] == 0


async def test_counter_grows_when_someone_else_comes_in(client):
    one, _ = await join(client, 1)
    await join(client, 2)
    update = await one.recv("online", timeout=4)
    assert update["online"] == 2


async def test_counter_sees_who_is_searching_and_who_is_playing(client):
    one, _ = await join(client, 1)
    two, _ = await join(client, 2)
    await one.send(t="find", duration=30, level="normal")
    await one.recv("queued")
    searching = await one.recv("online", timeout=4)
    while searching["searching"] == 0:
        searching = await one.recv("online", timeout=4)
    assert searching["searching"] == 1

    await two.send(t="find", duration=30, level="normal")
    await one.recv("found")
    playing = await one.recv("online", timeout=4)
    while playing["playing"] == 0:
        playing = await one.recv("online", timeout=4)
    assert playing["playing"] == 2
    assert playing["searching"] == 0, "ушедшие в матч в очереди не числятся"


async def test_counter_drops_when_someone_leaves(client):
    one, _ = await join(client, 1)
    two, _ = await join(client, 2)
    await one.recv("online", timeout=4)
    await two.close()
    update = await one.recv("online", timeout=4)
    while update["online"] != 1:
        update = await one.recv("online", timeout=4)
    assert update["online"] == 1


async def test_health_endpoint_answers(client):
    body = await (await client.get("/health")).json()
    assert body["ok"] is True and "players" in body


async def test_telegram_library_is_served_from_our_own_domain(client):
    """У части операторов telegram.org с телефона не открывается, и тогда в
    Mini App нет window.Telegram — игра не может узнать, кто зашёл."""
    path = client.hub.tg_script_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("// WebApp " + "x" * 3000)
    response = await client.get("/tg-webapp.js")
    assert response.status == 200
    assert "javascript" in response.headers["Content-Type"]
    assert "WebApp" in await response.text()


async def test_page_takes_the_library_from_us_and_telegram_as_backup(client):
    body = await (await client.get("/")).text()
    assert "/tg-webapp.js" in body
    assert "telegram.org/js/telegram-web-app.js" in body, "запасной путь тоже нужен"


async def test_mini_app_page_is_served(client):
    response = await client.get("/")
    assert response.status == 200
    assert "static/app.js" in await response.text()
