"""Пополнение вручную: чек, проверка админом и защита от десяти чеков."""
import sys
from pathlib import Path

import pytest
from aiogram.dispatcher.event.bases import SkipHandler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from handlers import payments, topup
from services import keyboards, panel_ui, texts
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings
from tests.test_engine import make_config

USER = 555
ADMIN = 99


class State:
    """Заглушка FSM: помнит состояние и данные."""

    def __init__(self) -> None:
        self.state = None
        self.data: dict = {}

    async def set_state(self, value):
        self.state = value

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def get_data(self):
        return dict(self.data)

    async def clear(self):
        self.state = None
        self.data = {}


class Message:
    def __init__(self, text="", user_id=USER, photo=False, document=False) -> None:
        self.text = text
        self.photo = [type("P", (), {"file_id": "photo-1"})()] if photo else None
        self.document = type("D", (), {"file_id": "doc-1"})() if document else None
        self.from_user = type(
            "U", (), {"id": user_id, "username": "nick", "first_name": "Ник"}
        )()
        self.chat = type("C", (), {"id": user_id, "type": "private"})()
        self.answers: list[str] = []
        self.caption = "чек"

    async def answer(self, text, **kwargs):
        self.answers.append(text)
        return self

    async def edit_text(self, text, **kwargs):
        self.answers.append(text)
        return self

    async def edit_caption(self, caption, **kwargs):
        self.answers.append(caption)
        return self


class Callback:
    def __init__(self, data, user_id=USER) -> None:
        self.data = data
        self.from_user = type(
            "U", (), {"id": user_id, "username": "nick", "first_name": "Ник"}
        )()
        self.message = Message(user_id=user_id)
        self.alerts: list[str] = []

    async def answer(self, text="", show_alert=False):
        self.alerts.append(text)


class Bot:
    def __init__(self) -> None:
        self.photos: list[tuple[int, str]] = []
        self.messages: list[tuple[int, str]] = []

    async def send_photo(self, chat_id, photo, caption="", **kwargs):
        self.photos.append((chat_id, caption))

    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append((chat_id, text))


@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "topup.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path, admin_ids=[ADMIN])
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    settings.set("manual_pay_enabled", True)
    settings.set("manual_pay_details", "8888 1111 2222 3333")
    settings.set("manual_pay_price", "1.5")
    settings.set("manual_pay_currency", "сомони")
    repo.upsert_user(USER, "nick", "Ник")
    return repo, config, settings, Bot()


async def send_receipt(env_tuple, state, votes=5):
    """Пройти путь целиком: «я оплатил» → фото чека."""
    repo, config, settings, bot = env_tuple
    await topup.ask_receipt(Callback(f"manual:receipt:{votes}"), repo, settings, state)
    message = Message(photo=True)
    await topup.take_receipt(message, bot, repo, config, settings, state)
    return message


# ------------------------------------------------------------- сумма

def test_the_amount_follows_the_price():
    assert texts.manual_amount(5, "1.5", "сомони") == "7.5 сомони"
    assert texts.manual_amount(1, "1,15", "сомони") == "1.15 сомони"
    assert texts.manual_amount(10, "2", "сомони") == "20 сомони"


def test_a_broken_price_does_not_break_the_screen():
    """Админ вписал ерунду — экран всё равно показывается."""
    assert "сомони" in texts.manual_amount(5, "дорого", "сомони")


# ------------------------------------------------------------- два шага

@pytest.mark.asyncio
async def test_the_first_screen_asks_how_many(env):
    """Сначала количество — реквизиты показываем уже с точной суммой."""
    _, _, settings, _ = env
    callback = Callback("manual:pick")

    await payments.manual_pick(callback, settings, State())

    shown = callback.message.answers[0]
    assert "Сколько голосов" in shown
    assert "1.5 сомони" in shown, "цена одного голоса берётся из панели"
    assert "8888" not in shown, "реквизиты — на следующем шаге"


@pytest.mark.asyncio
async def test_the_second_screen_shows_details_and_total(env):
    _, _, settings, _ = env
    callback = Callback("manual:5")

    await payments.manual_details(callback, settings, State())

    shown = callback.message.answers[0]
    assert "8888 1111 2222 3333" in shown
    assert "7.5 сомони" in shown, "5 голосов по 1.5"


@pytest.mark.asyncio
async def test_the_amount_can_be_changed_back(env):
    """С экрана реквизитов должен быть путь назад к выбору количества."""
    _, _, settings, _ = env
    markup = keyboards.manual_details("8888", 5)

    actions = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert "manual:pick" in actions


def test_the_button_carries_the_premium_icon():
    """ID иконки живёт отдельным полем, а символ уходит из подписи."""
    button = keyboards.manual_pay("Душанбе Сити", {"🏦": "5330540737777914038"})

    assert button.icon_custom_emoji_id == "5330540737777914038"
    assert button.text == "Душанбе Сити"
    assert button.callback_data == "manual:pick"


def test_the_button_survives_without_the_icon():
    button = keyboards.manual_pay("Душанбе Сити", {})

    assert button.text == "🏦 Душанбе Сити"
    assert button.icon_custom_emoji_id is None


# --------------------------------------------------- одна заявка на человека

@pytest.mark.asyncio
async def test_a_receipt_reaches_the_admin(env):
    repo, _, _, bot = env
    state = State()

    await send_receipt(env, state)

    assert bot.photos and bot.photos[0][0] == ADMIN
    assert repo.pending_topup(USER) is not None


@pytest.mark.asyncio
async def test_a_second_receipt_is_refused(env):
    """Десять чеков подряд — главное, от чего защищаемся."""
    repo, _, settings, _ = env
    state = State()
    await send_receipt(env, state)

    callback = Callback("manual:receipt:5")
    await topup.ask_receipt(callback, repo, settings, state)

    assert repo.topups("pending") and len(repo.topups("pending")) == 1
    assert any("проверке" in alert for alert in callback.alerts)


@pytest.mark.asyncio
async def test_a_forgotten_request_does_not_lock_the_person(env):
    """Нажал «я оплатил» и передумал — вторая попытка должна работать."""
    repo, _, settings, _ = env
    state = State()
    await topup.ask_receipt(Callback("manual:receipt:5"), repo, settings, state)

    callback = Callback("manual:receipt:10")
    await topup.ask_receipt(callback, repo, settings, state)

    waiting = repo.pending_topup(USER)
    assert len(repo.topups("pending")) == 1, "заявка та же, а не новая"
    assert int(waiting["votes"]) == 10, "количество должно обновиться"
    assert state.state == topup.Topup.waiting_receipt


@pytest.mark.asyncio
async def test_cancel_frees_the_person(env):
    repo, _, settings, _ = env
    state = State()
    await topup.ask_receipt(Callback("manual:receipt:5"), repo, settings, state)

    await topup.cancel(Callback("manual:cancel"), repo, state)

    assert repo.pending_topup(USER) is None


@pytest.mark.asyncio
async def test_a_sent_receipt_cannot_be_cancelled(env):
    """Отменять уже отправленный чек нельзя — иначе защита обходится."""
    repo, _, _, _ = env
    state = State()
    await send_receipt(env, state)

    assert repo.cancel_topup(USER) is False
    assert repo.pending_topup(USER) is not None


@pytest.mark.asyncio
async def test_a_command_lets_the_person_out(env):
    repo, _, settings, _ = env
    state = State()
    await topup.ask_receipt(Callback("manual:receipt:5"), repo, settings, state)

    with pytest.raises(SkipHandler):
        await topup.command_leaves_receipt(Message("/start"), repo, state)

    assert repo.pending_topup(USER) is None, "заявка не должна висеть после выхода"


@pytest.mark.asyncio
async def test_text_instead_of_a_photo_is_explained(env):
    message = Message("я оплатил честно")

    await topup.not_a_receipt(message)

    assert message.answers and "скриншот" in message.answers[0].lower()


# ------------------------------------------------------------- решение

@pytest.mark.asyncio
async def test_accepting_adds_votes(env):
    repo, config, _, bot = env
    state = State()
    await send_receipt(env, state, votes=10)
    topup_id = int(repo.pending_topup(USER)["id"])

    await topup.decide(Callback(f"topup:ok:{topup_id}", ADMIN), bot, repo, config)

    assert repo.vote_balance(USER) == 10
    assert repo.topup(topup_id)["status"] == "accepted"


@pytest.mark.asyncio
async def test_a_second_approval_does_not_pay_twice(env):
    """Два админа нажали одновременно — голоса начисляются один раз."""
    repo, config, _, bot = env
    state = State()
    await send_receipt(env, state, votes=10)
    topup_id = int(repo.pending_topup(USER)["id"])

    await topup.decide(Callback(f"topup:ok:{topup_id}", ADMIN), bot, repo, config)
    await topup.decide(Callback(f"topup:ok:{topup_id}", ADMIN), bot, repo, config)

    assert repo.vote_balance(USER) == 10


@pytest.mark.asyncio
async def test_declining_gives_nothing_and_frees_the_person(env):
    repo, config, _, bot = env
    state = State()
    await send_receipt(env, state)
    topup_id = int(repo.pending_topup(USER)["id"])

    await topup.decide(Callback(f"topup:no:{topup_id}", ADMIN), bot, repo, config)

    assert repo.vote_balance(USER) == 0
    assert repo.pending_topup(USER) is None, "после отказа можно подать заново"


@pytest.mark.asyncio
async def test_a_stranger_cannot_decide(env):
    repo, config, _, bot = env
    state = State()
    await send_receipt(env, state)
    topup_id = int(repo.pending_topup(USER)["id"])

    await topup.decide(Callback(f"topup:ok:{topup_id}", 12345), bot, repo, config)

    assert repo.vote_balance(USER) == 0
    assert repo.topup(topup_id)["status"] == "pending"


# ------------------------------------------------------- выключенный способ

@pytest.mark.asyncio
async def test_the_button_hides_without_details(env):
    """Реквизиты пустые — способ не предлагается, чтобы не платили в никуда."""
    _, _, settings, _ = env
    settings.set("manual_pay_details", "")

    assert payments._manual_on(settings) is False


@pytest.mark.asyncio
async def test_a_disabled_method_refuses_a_receipt(env):
    repo, _, settings, _ = env
    settings.set("manual_pay_enabled", False)
    callback = Callback("manual:receipt:5")

    await topup.ask_receipt(callback, repo, settings, State())

    assert repo.pending_topup(USER) is None
    assert any("недоступен" in alert for alert in callback.alerts)


# ------------------------------------------------------------- панель

def test_the_panel_warns_about_empty_details(env):
    _, _, settings, _ = env
    settings.set("manual_pay_details", "")
    text, _ = panel_ui.manual_pay(settings.all(), (0, 0, 0), [])

    assert "Реквизиты не заполнены" in text


def test_the_panel_counts_requests(env):
    repo, _, settings, _ = env
    repo.open_topup(USER, 5, "7.5 сомони")
    text, markup = panel_ui.manual_pay(
        settings.all(), repo.topup_stats(), repo.topups("pending")
    )

    assert "На проверке: <b>1</b>" in text
    assert any("#1" in button.text for row in markup.inline_keyboard for button in row)
