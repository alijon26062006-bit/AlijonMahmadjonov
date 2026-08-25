"""Чистка спама в группах. Каналы этим модулем не затрагиваются."""
import sys
from pathlib import Path

import pytest
from aiogram.dispatcher.event.bases import SkipHandler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from handlers import groups
from services import moderation, panel_ui
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings
from tests.test_engine import make_config

GROUP = -1002000000000


class Entity:
    def __init__(self, type_: str) -> None:
        self.type = type_


class Msg:
    def __init__(self, text="", user_id=7, is_bot=False, caption=None,
                 entities=None, forward_channel=False, via_bot=False,
                 new_members=None, chat_id=GROUP) -> None:
        self.text = text
        self.caption = caption
        self.entities = entities or []
        self.caption_entities = []
        self.chat = type("C", (), {"id": chat_id, "type": "supergroup", "title": "Чат"})()
        self.from_user = type(
            "U", (), {"id": user_id, "is_bot": is_bot, "username": "u", "first_name": "U"}
        )()
        self.via_bot = object() if via_bot else None
        self.new_chat_members = new_members
        self.deleted = False
        if forward_channel:
            self.forward_origin = type(
                "O", (), {"chat": type("C", (), {"type": "channel"})()}
            )()
        else:
            self.forward_origin = None

    async def delete(self):
        self.deleted = True


class Bot:
    def __init__(self, admins=()) -> None:
        self.admins = set(admins)
        self.banned: list[tuple[int, int]] = []
        self.sent: list[str] = []

    async def get_chat_member(self, chat_id, user_id):
        status = "administrator" if user_id in self.admins else "member"
        return type("M", (), {"status": status})()

    async def ban_chat_member(self, chat_id, user_id):
        self.banned.append((chat_id, user_id))

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append(text)


@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "groups.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path, admin_ids=[99])
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    repo.add_group(GROUP, "Чат")
    return repo, config, settings, Bot()


async def run(message, env_tuple, bot=None):
    """Прогнать сообщение через чистку. True — пропущено дальше."""
    repo, config, settings, default_bot = env_tuple
    try:
        await groups.clean_group(message, bot or default_bot, repo, config, settings)
    except SkipHandler:
        return True
    return False


# ------------------------------------------------------------- правила

def test_a_link_is_spam(env):
    _, _, settings, _ = env
    assert moderation.check(Msg("заходи t.me/casino"), settings)
    assert moderation.check(Msg("вот https://scam.site"), settings)


def test_a_hidden_link_is_found_too(env):
    """Ссылку прячут в разметку — в тексте её не видно."""
    _, _, settings, _ = env
    message = Msg("тут ничего такого", entities=[Entity("text_link")])

    assert moderation.check(message, settings)


def test_a_banned_word_is_spam(env):
    _, _, settings, _ = env
    assert moderation.check(Msg("продаю ИНТИМ услуги"), settings)
    assert moderation.check(Msg("взлом любого аккаунта"), settings)


def test_a_word_in_a_caption_is_found(env):
    _, _, settings, _ = env
    assert moderation.check(Msg("", caption="казино тут"), settings)


def test_a_forward_from_a_channel_is_spam(env):
    _, _, settings, _ = env
    assert moderation.check(Msg("реклама", forward_channel=True), settings)


def test_too_many_mentions(env):
    _, _, settings, _ = env
    assert moderation.check(Msg("@one_chan @two_chan @three_chan @four_chan"), settings)


def test_a_normal_message_survives(env):
    _, _, settings, _ = env
    assert not moderation.check(Msg("всем привет, когда следующий батл?"), settings)
    assert not moderation.check(Msg("я проголосовал за @nick"), settings)


def test_the_reason_is_always_named(env):
    _, _, settings, _ = env
    verdict = moderation.check(Msg("казино"), settings)

    assert verdict.reason, "за каждое удаление бот должен уметь назвать причину"


def test_links_can_be_allowed(env):
    """Ссылки разрешены — но от новичка всё равно удаляем."""
    _, _, settings, _ = env
    settings.set("spam_delete_links", False)

    assert not moderation.check(Msg("вот ссылка t.me/chat"), settings)
    assert moderation.check(Msg("вот ссылка t.me/chat"), settings, is_new=True)


# ------------------------------------------------------- удаление в группе

@pytest.mark.asyncio
async def test_spam_is_deleted(env):
    repo, _, _, _ = env
    message = Msg("казино тут t.me/x")

    passed = await run(message, env)

    assert message.deleted and not passed
    assert repo.group(GROUP)["deleted"] == 1


@pytest.mark.asyncio
async def test_a_clean_message_goes_further(env):
    """Чистое сообщение должно жить дальше: команды в группе не ломаем."""
    message = Msg("привет всем")

    passed = await run(message, env)

    assert passed and not message.deleted


@pytest.mark.asyncio
async def test_the_bot_admin_is_untouchable(env):
    message = Msg("казино t.me/x", user_id=99)  # 99 — админ бота

    passed = await run(message, env)

    assert passed and not message.deleted


@pytest.mark.asyncio
async def test_a_group_admin_is_untouchable(env):
    repo, config, settings, _ = env
    bot = Bot(admins={7})
    message = Msg("казино t.me/x", user_id=7)

    passed = await run(message, env, bot)

    assert passed and not message.deleted


@pytest.mark.asyncio
async def test_moderation_can_be_switched_off_per_group(env):
    repo, _, _, _ = env
    repo.toggle_group(GROUP)
    message = Msg("казино t.me/x")

    passed = await run(message, env)

    assert passed and not message.deleted


@pytest.mark.asyncio
async def test_an_unknown_group_registers_itself(env):
    repo, _, _, _ = env
    message = Msg("привет", chat_id=-1002999999999)

    await run(message, env)

    assert repo.group(-1002999999999) is not None


# ---------------------------------------------------------------- бан

@pytest.mark.asyncio
async def test_a_repeat_spammer_is_kicked(env):
    repo, _, settings, bot = env
    settings.set("spam_strike_limit", 3)

    for _ in range(3):
        await run(Msg("казино"), env, bot)

    assert bot.banned == [(GROUP, 7)]


@pytest.mark.asyncio
async def test_one_slip_does_not_get_you_kicked(env):
    _, _, _, bot = env

    await run(Msg("казино"), env, bot)

    assert bot.banned == []


@pytest.mark.asyncio
async def test_banning_can_be_switched_off(env):
    _, _, settings, bot = env
    settings.set("spam_strike_limit", 0)

    for _ in range(5):
        await run(Msg("казино"), env, bot)

    assert bot.banned == []


@pytest.mark.asyncio
async def test_a_failed_delete_does_not_count_a_strike(env):
    """Нет прав удалять — не наказываем человека за это."""
    repo, config, settings, bot = env

    class Stubborn(Msg):
        async def delete(self):
            from aiogram.exceptions import TelegramBadRequest

            raise TelegramBadRequest(method=None, message="not enough rights")

    await run(Stubborn("казино"), env, bot)

    assert repo.group(GROUP)["deleted"] == 0
    assert bot.banned == []


# --------------------------------------------------- добавление в группу

class Joined:
    def __init__(self, status="administrator", chat_id=GROUP, by=42) -> None:
        self.chat = type("C", (), {"id": chat_id, "type": "supergroup", "title": "Новый чат"})()
        self.new_chat_member = type("M", (), {"status": status})()
        self.from_user = type(
            "U", (), {"id": by, "username": "adder", "first_name": "A", "full_name": "A"}
        )() if by else None


@pytest.mark.asyncio
async def test_being_added_registers_the_group(env):
    repo, config, _, bot = env

    await groups.added_to_group(Joined(chat_id=-1002777777777), bot, repo, config)

    group = repo.group(-1002777777777)
    assert group is not None
    assert int(group["added_by"]) == 42, "должно быть видно, кто добавил"
    assert any("добавили в группу" in text for text in bot.sent)
    assert any("@adder" in text for text in bot.sent)


@pytest.mark.asyncio
async def test_without_admin_rights_the_owner_is_warned(env):
    repo, config, _, bot = env

    await groups.added_to_group(Joined(status="member", chat_id=-1002888888888), bot, repo, config)

    assert any("права администратора" in text for text in bot.sent)


@pytest.mark.asyncio
async def test_being_removed_forgets_the_group(env):
    repo, config, _, bot = env

    await groups.added_to_group(Joined(status="kicked"), bot, repo, config)

    assert repo.group(GROUP) is None


# --------------------------------------------------------------- панель

def test_the_panel_lists_groups(env):
    repo, _, settings, _ = env
    repo.count_deleted(GROUP)

    text, markup = panel_ui.groups(repo.groups(), settings.all())

    assert "Чат" in text and "удалено: 1" in text
    assert "Group Privacy" in text, "инструкция про @BotFather обязательна"


def test_the_panel_survives_an_empty_list(env):
    _, _, settings, _ = env
    text, markup = panel_ui.groups([], settings.all())

    assert text.strip() and markup.inline_keyboard


# ------------------------------------------------------- карточка группы

class InfoBot:
    """Телеграм, который рассказывает про группу."""

    def __init__(self, title="Чат батлов", username=None, invite=None,
                 members=128, status="administrator", can_delete=True,
                 can_restrict=True, fail=None) -> None:
        self.data = dict(
            title=title, username=username, invite_link=invite, members=members,
            status=status, can_delete=can_delete, can_restrict=can_restrict,
        )
        self.fail = fail

    async def me(self):
        return type("M", (), {"id": 4242})()

    async def get_chat(self, chat_id):
        if self.fail:
            from aiogram.exceptions import TelegramBadRequest

            raise TelegramBadRequest(method=None, message=self.fail)
        d = self.data
        return type("C", (), {
            "title": d["title"], "username": d["username"], "invite_link": d["invite_link"],
        })()

    async def get_chat_member_count(self, chat_id):
        return self.data["members"]

    async def get_chat_member(self, chat_id, user_id):
        d = self.data
        return type("M", (), {
            "status": d["status"],
            "can_delete_messages": d["can_delete"],
            "can_restrict_members": d["can_restrict"],
        })()


@pytest.mark.asyncio
async def test_the_card_shows_size_and_rights(env):
    from services import group_info

    card = await group_info.describe(InfoBot(members=128), GROUP)

    assert card["members"] == 128
    assert card["rights"] == {"удалять сообщения": True, "banить участников": True}
    assert card["missing"] == []


@pytest.mark.asyncio
async def test_the_card_names_missing_rights(env):
    from services import group_info

    card = await group_info.describe(InfoBot(can_delete=False), GROUP)

    assert "удалять сообщения" in card["missing"]


@pytest.mark.asyncio
async def test_a_public_group_gives_a_link(env):
    from services import group_info

    card = await group_info.describe(InfoBot(username="battlechat"), GROUP)
    assert card["link"] == "https://t.me/battlechat"


@pytest.mark.asyncio
async def test_a_private_group_falls_back_to_the_invite(env):
    from services import group_info

    card = await group_info.describe(InfoBot(invite="https://t.me/+abc"), GROUP)
    assert card["link"] == "https://t.me/+abc"


@pytest.mark.asyncio
async def test_a_lost_group_says_so_instead_of_crashing(env):
    from services import group_info

    card = await group_info.describe(InfoBot(fail="chat not found"), GROUP)

    assert card["error"] and card["members"] is None


@pytest.mark.asyncio
async def test_the_card_screen_reads_well(env):
    repo, _, _, _ = env
    from services import group_info

    repo.count_deleted(GROUP)
    card = await group_info.describe(InfoBot(username="battlechat"), GROUP)
    text, markup = panel_ui.group_card(card, repo.group(GROUP), None)

    assert "128" in text and "Удалено сообщений: <b>1</b>" in text
    labels = [b.text for row in markup.inline_keyboard for b in row]
    assert any("Открыть группу" in label for label in labels)
    assert any("Выйти из группы" in label for label in labels)


@pytest.mark.asyncio
async def test_the_card_warns_about_missing_delete_right(env):
    repo, _, _, _ = env
    from services import group_info

    card = await group_info.describe(InfoBot(can_delete=False), GROUP)
    text, _ = panel_ui.group_card(card, repo.group(GROUP), None)

    assert "чистка не работает" in text


@pytest.mark.asyncio
async def test_the_card_shows_who_added_the_bot(env):
    repo, _, _, _ = env
    from services import group_info

    repo.upsert_user(42, "adder", "A")
    card = await group_info.describe(InfoBot(), GROUP)
    text, _ = panel_ui.group_card(card, repo.group(GROUP), repo.get_user(42))

    assert "@adder" in text


@pytest.mark.asyncio
async def test_a_lost_group_card_still_offers_to_leave(env):
    repo, _, _, _ = env
    from services import group_info

    card = await group_info.describe(InfoBot(fail="chat not found"), GROUP)
    text, markup = panel_ui.group_card(card, repo.group(GROUP), None)

    assert "не видит эту группу" in text
    assert markup.inline_keyboard, "кнопки должны остаться"


def test_the_list_opens_the_card_not_the_toggle(env):
    """Нажатие на группу открывает карточку — переключатель уже внутри неё."""
    repo, _, settings, _ = env
    _, markup = panel_ui.groups(repo.groups(), settings.all())
    actions = [b.callback_data for row in markup.inline_keyboard for b in row]

    assert f"p:groups:card:{GROUP}" in actions
