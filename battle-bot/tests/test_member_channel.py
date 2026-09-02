"""Личный канал участника: подключение, публикация пары и итога."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import MSK
from core.engine import BattleEngine
from core.models import Player, Slot
from handlers import mychannel
from services import links, member_channel, texts
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings
from tests.test_engine import make_config

CHANNEL = -1009999999999


class Me:
    id = 4242


class Member:
    def __init__(self, status, can_post=True) -> None:
        self.status = status
        self.can_post_messages = can_post


class Bot:
    """Телеграм для личных каналов: кто где админ и что ушло в эфир."""

    def __init__(self, members=None, dead_chats=()) -> None:
        # (chat_id, user_id) -> Member
        self.members = members if members is not None else {}
        self.dead_chats = set(dead_chats)
        self.sent: list[tuple[int, str, object]] = []

    async def me(self):
        return Me()

    async def get_chat_member(self, chat_id, user_id):
        member = self.members.get((chat_id, user_id))
        if member is None:
            raise TelegramBadRequest(method=None, message="chat not found")
        return member

    async def send_message(self, chat_id, text, reply_markup=None, **kwargs):
        if chat_id in self.dead_chats:
            raise TelegramForbiddenError(method=None, message="bot is not a member")
        self.sent.append((chat_id, text, reply_markup))
        return object()

    def to(self, chat_id) -> list[str]:
        return [text for cid, text, _ in self.sent if cid == chat_id]


def admin_bot(owner_id: int, chat_id: int = CHANNEL, **kwargs) -> Bot:
    """Бот-администратор канала, владелец которого — owner_id."""
    return Bot(
        members={
            (chat_id, Me.id): Member("administrator", can_post=True),
            (chat_id, owner_id): Member("creator"),
        },
        **kwargs,
    )


@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "mych.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path)
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    for uid in (1, 2):
        repo.upsert_user(uid, f"nick{uid}", f"N{uid}")
    return repo, config, settings


def open_match(repo: Repo, hours: int = 3) -> int:
    deadline = datetime.now(MSK) + timedelta(hours=hours)
    battle_id = repo.create_battle(deadline)
    return repo.create_match(
        battle_id, 1, 1, [Player(1, "nick1"), Player(2, "nick2")],
        advance=1, is_final=False, deadline=deadline,
    )


# ------------------------------------------------------- разбор пересылки

class Chat:
    def __init__(self, chat_id, chat_type="channel", title="Мой канал", username="mine"):
        self.id, self.type, self.title, self.username = chat_id, chat_type, title, username


class Origin:
    def __init__(self, chat=None) -> None:
        self.chat = chat


class Msg:
    def __init__(self, origin=None) -> None:
        self.forward_origin = origin


def test_a_forwarded_channel_post_gives_the_channel():
    chat_id, title, username, problem = member_channel.from_forward(Msg(Origin(Chat(CHANNEL))))

    assert (chat_id, title, username, problem) == (CHANNEL, "Мой канал", "mine", "")


def test_a_plain_message_is_refused():
    _, _, _, problem = member_channel.from_forward(Msg())
    assert "не пост из канала" in problem


def test_a_forward_from_a_group_is_refused():
    _, _, _, problem = member_channel.from_forward(Msg(Origin(Chat(-500, "supergroup"))))
    assert "не пост из канала" in problem


def test_a_hidden_author_is_explained():
    """Скрытая пересылка не показывает канал — человеку нужно это объяснить."""
    _, _, _, problem = member_channel.from_forward(Msg(Origin()))
    assert "скрыт" in problem


# ------------------------------------------------------------- права бота

@pytest.mark.asyncio
async def test_an_admin_bot_in_the_owners_channel_may_publish():
    assert await member_channel.can_publish(admin_bot(1), CHANNEL, 1) == ""


@pytest.mark.asyncio
async def test_a_bot_outside_the_channel_may_not():
    problem = await member_channel.can_publish(Bot(), CHANNEL, 1)
    assert "не администратор" in problem


@pytest.mark.asyncio
async def test_an_admin_without_posting_rights_may_not():
    bot = Bot(members={
        (CHANNEL, Me.id): Member("administrator", can_post=False),
        (CHANNEL, 1): Member("creator"),
    })
    assert "Публикация сообщений" in await member_channel.can_publish(bot, CHANNEL, 1)


@pytest.mark.asyncio
async def test_a_stranger_cannot_claim_someone_elses_channel():
    """Переслать чужой пост может кто угодно — привязать канал только владелец."""
    bot = Bot(members={
        (CHANNEL, Me.id): Member("administrator"),
        (CHANNEL, 1): Member("left"),
    })
    assert "не ваш канал" in await member_channel.can_publish(bot, CHANNEL, 1)


# --------------------------------------------------------------- публикация

@pytest.mark.asyncio
async def test_the_pair_is_published_with_a_vote_for_me_button(env):
    repo, config, settings = env
    repo.link_channel(1, CHANNEL, "Мой канал", "mine")
    match_id = open_match(repo)
    bot = admin_bot(1)

    assert await member_channel.publish_match(bot, repo, config, settings, 1, match_id)

    chat_id, body, markup = bot.sent[0]
    assert chat_id == CHANNEL
    assert "nick1" in body and "nick2" in body
    button = markup.inline_keyboard[0][0]
    assert button.url == links.vote_link(config.bot_username, match_id, 1)
    assert "за меня" in button.text
    assert int(repo.member_channel(1)["posts"]) == 1


@pytest.mark.asyncio
async def test_the_link_points_at_the_owner_not_the_rival(env):
    """Кнопка в канале ведёт голосовать именно за хозяина канала."""
    repo, config, settings = env
    repo.link_channel(2, CHANNEL, "Канал второго", None)
    match_id = open_match(repo)
    bot = admin_bot(2)

    await member_channel.publish_match(bot, repo, config, settings, 2, match_id)

    url = bot.sent[0][2].inline_keyboard[0][0].url
    assert url.endswith(f"v{match_id}_2")
    assert links.vote_target(f"v{match_id}_2") == 2


@pytest.mark.asyncio
async def test_nothing_is_published_without_a_linked_channel(env):
    repo, config, settings = env
    bot = admin_bot(1)

    assert not await member_channel.publish_match(bot, repo, config, settings, 1, open_match(repo))
    assert bot.sent == []


@pytest.mark.asyncio
async def test_the_admin_switch_stops_publishing(env):
    repo, config, settings = env
    repo.link_channel(1, CHANNEL, "Мой канал", None)
    settings.set("member_channels_enabled", False)
    bot = admin_bot(1)

    assert not await member_channel.publish_match(bot, repo, config, settings, 1, open_match(repo))
    assert bot.sent == []


@pytest.mark.asyncio
async def test_a_closed_match_is_not_advertised(env):
    repo, config, settings = env
    repo.link_channel(1, CHANNEL, "Мой канал", None)
    match_id = open_match(repo)
    repo.close_match(match_id, [Slot(1, "nick1", 3, 1), Slot(2, "nick2", 1, 2)])

    assert not await member_channel.publish_match(admin_bot(1), repo, config, settings, 1, match_id)


@pytest.mark.asyncio
async def test_losing_rights_disables_the_channel_and_warns_the_owner(env):
    """Бота выгнали из канала — привязка гаснет, владелец узнаёт об этом."""
    repo, config, settings = env
    repo.link_channel(1, CHANNEL, "Мой канал", None)
    bot = admin_bot(1, dead_chats=[CHANNEL])

    assert not await member_channel.publish_match(bot, repo, config, settings, 1, open_match(repo))
    assert int(repo.member_channel(1)["active"]) == 0
    assert "Верните права" in bot.to(1)[0]


@pytest.mark.asyncio
async def test_a_loser_sees_the_full_table_in_his_channel(env):
    repo, config, settings = env
    repo.link_channel(2, CHANNEL, "Канал второго", None)
    bot = admin_bot(2)
    ranking = [Slot(1, "nick1", 9, 1), Slot(2, "nick2", 2, 2)]

    await member_channel.publish_result(bot, repo, settings, 2, 1, False, ranking)

    body = bot.to(CHANNEL)[0]
    assert "Вылетел" in body
    assert "nick1" in body and "nick2" in body, "счёт соперника тоже виден"


@pytest.mark.asyncio
async def test_a_winner_is_congratulated_in_his_channel(env):
    repo, config, settings = env
    repo.link_channel(1, CHANNEL, "Мой канал", None)
    bot = admin_bot(1)
    ranking = [Slot(1, "nick1", 9, 1), Slot(2, "nick2", 2, 2)]

    await member_channel.publish_result(bot, repo, settings, 1, 1, False, ranking)

    assert "Прошёл дальше" in bot.to(CHANNEL)[0]


@pytest.mark.asyncio
async def test_a_rejected_premium_emoji_does_not_cost_the_channel(env):
    """Отказ по оформлению правами не лечится — гасить привязку нельзя."""
    repo, config, settings = env
    repo.link_channel(1, CHANNEL, "Мой канал", None)
    match_id = open_match(repo)

    class Picky(Bot):
        def __init__(self) -> None:
            super().__init__(members=admin_bot(1).members)
            self.tries = 0

        async def send_message(self, chat_id, text, reply_markup=None, **kwargs):
            self.tries += 1
            if self.tries == 1:
                raise TelegramBadRequest(
                    method=None, message="can't parse entities: unsupported custom emoji"
                )
            return await super().send_message(chat_id, text, reply_markup, **kwargs)

    bot, skip = Picky(), set()
    assert await member_channel.publish_match(
        bot, repo, config, settings, 1, match_id, skip
    )
    assert bot.tries == 2, "второй заход — обычными эмодзи"
    assert CHANNEL in skip
    assert int(repo.member_channel(1)["active"]) == 1, "привязка должна остаться живой"


@pytest.mark.asyncio
async def test_a_random_failure_skips_the_post_but_keeps_the_channel(env):
    repo, config, settings = env
    repo.link_channel(1, CHANNEL, "Мой канал", None)

    class Flaky(Bot):
        async def send_message(self, chat_id, text, reply_markup=None, **kwargs):
            raise TelegramBadRequest(method=None, message="message is too long")

    bot = Flaky(members=admin_bot(1).members)
    assert not await member_channel.publish_match(
        bot, repo, config, settings, 1, open_match(repo), set()
    )
    assert int(repo.member_channel(1)["active"]) == 1


# ------------------------------------------------------------ один владелец

def test_one_channel_belongs_to_one_person(env):
    repo, _, _ = env

    assert repo.link_channel(1, CHANNEL, "Канал", None)
    assert not repo.link_channel(2, CHANNEL, "Канал", None)
    assert repo.member_channel(2) is None


def test_relinking_your_own_channel_is_fine(env):
    repo, _, _ = env
    repo.link_channel(1, CHANNEL, "Старое имя", None)
    repo.disable_channel(1)

    assert repo.link_channel(1, CHANNEL, "Новое имя", "new")
    channel = repo.member_channel(1)
    assert channel["title"] == "Новое имя" and int(channel["active"]) == 1


def test_stats_count_live_channels_and_posts(env):
    repo, _, _ = env
    repo.link_channel(1, CHANNEL, "A", None)
    repo.link_channel(2, -1008888888888, "B", None)
    repo.bump_channel_posts(1)
    repo.bump_channel_posts(1)
    repo.disable_channel(2)

    assert repo.member_channel_stats() == (2, 1, 2)


# ---------------------------------------------------------------- сценарий

class State:
    """Ожидание пересылки — как у настоящего бота в этот момент."""

    def __init__(self, value=mychannel.MyChannel.waiting_forward) -> None:
        self.value = value

    async def set_state(self, value) -> None:
        self.value = value

    async def get_state(self):
        return self.value

    async def clear(self) -> None:
        self.value = None


class ForwardMsg:
    def __init__(self, bot, user_id, origin) -> None:
        self.bot = bot
        self.from_user = type("U", (), {"id": user_id, "username": "n", "first_name": "N"})()
        self.forward_origin = origin
        self.sent: list[str] = []

    async def answer(self, text, **kwargs):
        self.sent.append(text)


@pytest.mark.asyncio
async def test_forwarding_a_post_links_the_channel(env):
    repo, config, settings = env
    message = ForwardMsg(admin_bot(1), 1, Origin(Chat(CHANNEL)))

    await mychannel.take_forward(message, repo, config, settings, State())

    assert repo.member_channel(1) is not None
    assert "подключён" in message.sent[0]


@pytest.mark.asyncio
async def test_forwarding_someone_elses_channel_links_nothing(env):
    repo, config, settings = env
    bot = Bot(members={
        (CHANNEL, Me.id): Member("administrator"),
        (CHANNEL, 1): Member("member"),
    })
    message = ForwardMsg(bot, 1, Origin(Chat(CHANNEL)))

    await mychannel.take_forward(message, repo, config, settings, State())

    assert repo.member_channel(1) is None


@pytest.mark.asyncio
async def test_a_taken_channel_is_refused(env):
    repo, config, settings = env
    repo.link_channel(2, CHANNEL, "Канал", None)
    message = ForwardMsg(admin_bot(1), 1, Origin(Chat(CHANNEL)))

    await mychannel.take_forward(message, repo, config, settings, State())

    assert repo.member_channel(1) is None
    assert "другому участнику" in message.sent[0]


# -------------------------------------------------------- в ходе батла

class EngineBot:
    """Считает, что ушло в каждый чат: канал батлов, личка, каналы участников."""

    def __init__(self, members) -> None:
        self.members = members
        self.sent: dict[int, list[str]] = {}

    async def me(self):
        return Me()

    async def get_chat_member(self, chat_id, user_id):
        member = self.members.get((chat_id, user_id))
        if member is None:
            raise TelegramBadRequest(method=None, message="chat not found")
        return member

    async def send_message(self, chat_id, text, reply_markup=None, **kwargs):
        self.sent.setdefault(chat_id, []).append(text)
        return type("M", (), {"message_id": 777})()

    async def edit_message_text(self, **kwargs):
        return None


@pytest.mark.asyncio
async def test_a_started_round_reaches_the_participants_channel(tmp_path):
    """Батл начался — пара сама появилась в канале участника."""
    path = str(tmp_path / "flow.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path, min_participants=2)
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    bot = EngineBot({
        (CHANNEL, Me.id): Member("administrator"),
        (CHANNEL, 1): Member("creator"),
    })
    engine = BattleEngine(bot, repo, config, settings=settings)

    for uid in (1, 2):
        repo.upsert_user(uid, f"nick{uid}", f"N{uid}")
        await engine.join(uid, f"nick{uid}")
    repo.link_channel(1, CHANNEL, "Мой канал", None)

    started, _ = await engine.create_from_queue()

    assert started
    assert CHANNEL in bot.sent, "пара должна уйти в личный канал участника"
    assert "Я в батле" in bot.sent[CHANNEL][0]
    assert "nick2" in bot.sent[CHANNEL][0], "в посте виден соперник"
    assert int(repo.member_channel(1)["posts"]) == 1


@pytest.mark.asyncio
async def test_the_round_result_reaches_the_participants_channel(tmp_path):
    path = str(tmp_path / "flow2.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path, min_participants=2)
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    bot = EngineBot({
        (CHANNEL, Me.id): Member("administrator"),
        (CHANNEL, 1): Member("creator"),
    })
    engine = BattleEngine(bot, repo, config, settings=settings)

    for uid in (1, 2):
        repo.upsert_user(uid, f"nick{uid}", f"N{uid}")
        await engine.join(uid, f"nick{uid}")
    repo.link_channel(1, CHANNEL, "Мой канал", None)
    await engine.create_from_queue()
    before = len(bot.sent[CHANNEL])

    await engine.close_round(force=True)

    assert len(bot.sent[CHANNEL]) > before, "итог тоже должен уйти в канал"


@pytest.mark.asyncio
async def test_a_broken_channel_does_not_stop_the_battle(tmp_path):
    """Канал участника отвалился — батл всё равно идёт дальше."""
    path = str(tmp_path / "flow3.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path, min_participants=2)
    settings = Settings(repo.conn, config)
    settings.bootstrap()

    class Broken(EngineBot):
        async def send_message(self, chat_id, text, reply_markup=None, **kwargs):
            if chat_id == CHANNEL:
                raise TelegramForbiddenError(method=None, message="bot is not a member")
            return await super().send_message(chat_id, text, reply_markup, **kwargs)

    bot = Broken({})
    engine = BattleEngine(bot, repo, config, settings=settings)
    for uid in (1, 2):
        repo.upsert_user(uid, f"nick{uid}", f"N{uid}")
        await engine.join(uid, f"nick{uid}")
    repo.link_channel(1, CHANNEL, "Мой канал", None)

    started, _ = await engine.create_from_queue()

    assert started
    assert int(repo.member_channel(1)["active"]) == 0
    assert repo.current_battle() is not None


def test_the_publish_button_hides_when_the_feature_is_off():
    """Мёртвых кнопок быть не должно: выключено — значит не показываем."""
    from services import keyboards

    config = make_config()
    on = keyboards.my_match(7, config, None, own_channel=True)
    off = keyboards.my_match(7, config, None, own_channel=False)

    def has_publish(markup):
        return any(
            b.callback_data == "mych:post:7"
            for row in markup.inline_keyboard for b in row
        )

    assert has_publish(on) and not has_publish(off)


# ------------------------------------------------- приход по личной ссылке

def test_the_voting_screen_marks_who_you_were_called_for():
    from services import keyboards

    slots = [Slot(1, "nick1", 0, None), Slot(2, "nick2", 0, None)]
    markup = keyboards.voting(7, slots, make_config(), None, called_for=2)
    labels = [b.text for row in markup.inline_keyboard for b in row]

    assert any(label.startswith("🔥") and "nick2" in label for label in labels)
    assert not any(label.startswith("🔥") and "nick1" in label for label in labels)


def test_the_call_is_honest_about_the_choice():
    body = texts.called_to_support("nick1")
    assert "nick1" in body and "выбирайте кого хотите" in body
