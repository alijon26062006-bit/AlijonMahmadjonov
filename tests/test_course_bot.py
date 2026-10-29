"""Бот курса: рассказ о курсе, покупка по чеку, одноразовая ссылка в канал."""

import importlib
import time
from datetime import datetime

import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods import (
    AnswerCallbackQuery,
    CopyMessage,
    CreateChatInviteLink,
    EditMessageText,
    GetChatMember,
    SendMessage,
)
from aiogram.types import (
    CallbackQuery,
    Chat,
    ChatInviteLink,
    ChatMemberAdministrator,
    ChatMemberLeft,
    ChatMemberMember,
    ChatMemberUpdated,
    Message,
    MessageId,
    MessageOriginChannel,
    PhotoSize,
    Update,
    User,
)

from course_bot import admin, content, db, handlers, main, subscriptions
from course_bot.config import Config

TOKEN = "42:TESTTESTTESTTESTTESTTESTTESTTESTTEST"
ADMIN = 111
STUDENT = 222
OTHER = 333
CHANNEL = -1001234567890


class FakeTelegram:
    """Вместо Telegram: запоминает вызовы и отвечает правдоподобно."""

    def __init__(self):
        self.sent = []
        self.member_status = "left"   # кем числится ученик в канале
        self.bot_can_invite = True

    async def __call__(self, bot, method, timeout=None):
        self.sent.append(method)
        user = User(id=STUDENT, is_bot=False, first_name="Ученик")
        if isinstance(method, CopyMessage):
            return MessageId(message_id=77)
        if isinstance(method, CreateChatInviteLink):
            return ChatInviteLink(invite_link="https://t.me/+once", creator=User(id=42, is_bot=True, first_name="b"),
                                  creates_join_request=False, is_primary=False, is_revoked=False,
                                  name=method.name, member_limit=method.member_limit)
        if isinstance(method, GetChatMember):
            if method.user_id == 42:
                return ChatMemberAdministrator(
                    user=User(id=42, is_bot=True, first_name="b"), can_be_edited=False, is_anonymous=False,
                    can_manage_chat=True, can_delete_messages=True, can_manage_video_chats=True,
                    can_restrict_members=True, can_promote_members=False, can_change_info=True,
                    can_invite_users=self.bot_can_invite, can_post_stories=False, can_edit_stories=False,
                    can_delete_stories=False, can_send_welcome_messages=False)
            if self.member_status == "member":
                return ChatMemberMember(user=user)
            return ChatMemberLeft(user=user)
        if isinstance(method, (AnswerCallbackQuery,)):
            return True
        return Message(message_id=1, date=datetime.now(), chat=Chat(id=1, type="private"),
                       text=getattr(method, "text", None))

    async def close(self):
        pass

    def of(self, kind):
        return [m for m in self.sent if isinstance(m, kind)]

    def texts_to(self, chat_id):
        return [m.text for m in self.of(SendMessage) if m.chat_id == chat_id]


@pytest.fixture
def stand(tmp_path):
    importlib.reload(handlers)
    importlib.reload(admin)
    importlib.reload(subscriptions)
    importlib.reload(main)
    conn = db.connect(tmp_path / "course.db")
    config = Config(token=TOKEN, admin_ids=frozenset({ADMIN}), db_path=tmp_path / "course.db")
    bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    bot.session = FakeTelegram()
    dispatcher = main.build_dispatcher(config, conn)
    yield dispatcher, bot, bot.session, conn
    conn.close()


_ids = iter(range(1, 10_000))


def _user(user_id):
    return User(id=user_id, is_bot=False, first_name="Админ" if user_id == ADMIN else "Ученик",
                username=f"u{user_id}")


def _msg(user_id, **kw):
    n = next(_ids)
    return Message(message_id=n, date=datetime.now(), chat=Chat(id=user_id, type="private"),
                   from_user=_user(user_id), **kw)


def text(t, user_id=STUDENT):
    return Update(update_id=next(_ids), message=_msg(user_id, text=t))


def photo(user_id=STUDENT):
    sizes = [PhotoSize(file_id="p", file_unique_id="u", width=800, height=600)]
    return Update(update_id=next(_ids), message=_msg(user_id, photo=sizes))


def press(data, user_id=STUDENT, html="🧾 <b>Новый чек</b>"):
    return Update(update_id=next(_ids), callback_query=CallbackQuery(
        id=str(next(_ids)), from_user=_user(user_id), chat_instance="c", data=data,
        message=_msg(user_id, text=html)))


async def feed(dispatcher, bot, *updates):
    for u in updates:
        await dispatcher.feed_update(bot, u)


def ready_to_sell(conn):
    db.set_setting(conn, "pay", "Карта: 1234")
    db.set_setting(conn, "price", "300 сомони")
    db.set_setting(conn, "channel_id", str(CHANNEL))


async def test_start_shows_menu_with_buy(stand):
    dispatcher, bot, tg, conn = stand
    await feed(dispatcher, bot, text("/start"))
    msg = tg.of(SendMessage)[-1]
    assert "Python с нуля" in msg.text
    buttons = [b.callback_data for row in msg.reply_markup.inline_keyboard for b in row]
    assert "m:buy" in buttons and "m:program" in buttons
    assert db.status_of(conn, STUDENT) == "new"


async def test_program_lists_every_lesson_and_marks_ready(stand):
    dispatcher, bot, tg, conn = stand
    db.set_setting(conn, "ready", "2")
    await feed(dispatcher, bot, press("mod:0"))
    edited = tg.of(EditMessageText)[-1].text
    assert "✅ Урок 1. Установка Python и VS Code" in edited
    assert "✅ Урок 2. Команда print()" in edited
    assert "⏳ Урок 3. Переменные" in edited
    assert content.TOTAL_LESSONS == 65


async def test_buy_without_requisites_says_not_configured(stand):
    dispatcher, bot, tg, conn = stand
    await feed(dispatcher, bot, press("m:buy"))
    assert tg.of(EditMessageText)[-1].text == content.PAY_NOT_SET


async def test_full_purchase_gives_one_time_link(stand):
    dispatcher, bot, tg, conn = stand
    ready_to_sell(conn)
    await feed(dispatcher, bot, text("/start"), press("m:buy"))
    assert "Карта: 1234" in tg.of(EditMessageText)[-1].text

    await feed(dispatcher, bot, press("paid"))
    assert db.status_of(conn, STUDENT) == "waiting_receipt"

    await feed(dispatcher, bot, photo())
    assert db.status_of(conn, STUDENT) == "pending"
    copy = tg.of(CopyMessage)[-1]
    assert copy.chat_id == ADMIN and copy.from_chat_id == STUDENT
    card = [m for m in tg.of(SendMessage) if m.chat_id == ADMIN][-1]
    assert card.reply_markup.inline_keyboard[0][0].callback_data == f"ok:{STUDENT}"
    assert content.RECEIPT_RECEIVED in tg.texts_to(STUDENT)

    await feed(dispatcher, bot, press(f"ok:{STUDENT}", user_id=ADMIN))
    link = tg.of(CreateChatInviteLink)[-1]
    assert link.chat_id == CHANNEL and link.member_limit == 1 and link.name == f"id{STUDENT}"
    assert link.expire_date is not None
    assert any("https://t.me/+once" in t for t in tg.texts_to(STUDENT))
    assert db.status_of(conn, STUDENT) == "paid"
    assert "Подтверждено" in tg.of(EditMessageText)[-1].text

    # повторное нажатие не выдаёт вторую ссылку
    await feed(dispatcher, bot, press(f"ok:{STUDENT}", user_id=ADMIN))
    assert len(tg.of(CreateChatInviteLink)) == 1


async def test_reject_lets_student_try_again(stand):
    dispatcher, bot, tg, conn = stand
    ready_to_sell(conn)
    await feed(dispatcher, bot, text("/start"), press("paid"), photo(), press(f"no:{STUDENT}", user_id=ADMIN))
    assert db.status_of(conn, STUDENT) == "rejected"
    assert content.REJECTED in tg.texts_to(STUDENT)
    assert not tg.of(CreateChatInviteLink)

    await feed(dispatcher, bot, press("paid"), photo())
    assert db.status_of(conn, STUDENT) == "pending"


async def test_photo_without_pressing_paid_is_not_a_receipt(stand):
    dispatcher, bot, tg, conn = stand
    ready_to_sell(conn)
    await feed(dispatcher, bot, text("/start"), photo())
    assert not tg.of(CopyMessage)
    assert content.PRESS_BUY_FIRST in tg.texts_to(STUDENT)


async def test_approve_without_channel_keeps_receipt_pending(stand):
    dispatcher, bot, tg, conn = stand
    db.set_setting(conn, "pay", "Карта: 1234")
    await feed(dispatcher, bot, text("/start"), press("paid"), photo(), press(f"ok:{STUDENT}", user_id=ADMIN))
    assert db.status_of(conn, STUDENT) == "pending"
    assert not tg.of(CreateChatInviteLink)


async def test_student_cannot_use_admin_powers(stand):
    dispatcher, bot, tg, conn = stand
    ready_to_sell(conn)
    await feed(dispatcher, bot, text("/start"), press("set:price"), text("1 сомони"), press("adm:give"),
               text(str(STUDENT)))
    assert db.get_setting(conn, "price") == "300 сомони"
    assert db.status_of(conn, STUDENT) == "new"

    await feed(dispatcher, bot, press("paid"), photo(), press(f"ok:{STUDENT}"))
    assert db.status_of(conn, STUDENT) == "pending"
    assert not tg.of(CreateChatInviteLink)


async def test_only_admin_sees_admin_panel_button(stand):
    dispatcher, bot, tg, conn = stand
    await feed(dispatcher, bot, text("/start"), text("/start", user_id=ADMIN))
    student_menu, admin_menu = [m.reply_markup for m in tg.of(SendMessage)[-2:]]
    data = lambda kb: [b.callback_data for row in kb.inline_keyboard for b in row]  # noqa: E731
    assert "adm" not in data(student_menu)
    assert "adm" in data(admin_menu)


async def test_admin_sets_everything_with_buttons(stand):
    dispatcher, bot, tg, conn = stand
    await feed(dispatcher, bot,
               press("set:pay", user_id=ADMIN), text("Карта Алиф: 1111\nПолучатель: Алиджон", user_id=ADMIN),
               press("set:ready", user_id=ADMIN), text("100", user_id=ADMIN), text("5", user_id=ADMIN),
               press("set:contact", user_id=ADMIN), text("@alijon_admin", user_id=ADMIN),
               press("set:demo", user_id=ADMIN), text("https://example.com/urok1", user_id=ADMIN))
    assert db.get_setting(conn, "pay") == "Карта Алиф: 1111\nПолучатель: Алиджон"
    assert db.get_setting(conn, "ready") == "5"
    assert db.get_setting(conn, "contact") == "alijon_admin"
    assert db.get_setting(conn, "demo") == "https://example.com/urok1"

    # «-» убирает необязательную настройку
    await feed(dispatcher, bot, press("set:demo", user_id=ADMIN), text("-", user_id=ADMIN))
    assert db.get_setting(conn, "demo") == ""

    # «Отмена» — следующее сообщение уже не считается значением
    await feed(dispatcher, bot, press("set:price", user_id=ADMIN), press("adm", user_id=ADMIN),
               text("просто текст", user_id=ADMIN))
    assert db.get_setting(conn, "price") == db.DEFAULTS["price"]


async def test_forwarded_channel_post_connects_channel(stand):
    dispatcher, bot, tg, conn = stand
    origin = MessageOriginChannel(type="channel", date=datetime.now(), message_id=5,
                                  chat=Chat(id=CHANNEL, type="channel", title="Курс"))
    await feed(dispatcher, bot, Update(update_id=next(_ids), message=_msg(ADMIN, text="пост", forward_origin=origin)))
    assert db.get_setting(conn, "channel_id") == str(CHANNEL)

    db.set_setting(conn, "channel_id", "")
    tg.bot_can_invite = False
    await feed(dispatcher, bot, Update(update_id=next(_ids), message=_msg(ADMIN, text="пост", forward_origin=origin)))
    assert db.get_setting(conn, "channel_id") == ""


async def test_give_grants_access_manually(stand):
    dispatcher, bot, tg, conn = stand
    ready_to_sell(conn)
    await feed(dispatcher, bot, text("/start"), press("adm:give", user_id=ADMIN), text("999", user_id=ADMIN))
    assert not tg.of(CreateChatInviteLink)   # такого ученика нет
    await feed(dispatcher, bot, text(str(STUDENT), user_id=ADMIN))
    assert db.status_of(conn, STUDENT) == "paid"
    assert tg.of(CreateChatInviteLink)


# ── подписка на месяц ───────────────────────────────────────────────────────

DAY = 86400


def active_student(conn, days_left=20.0):
    db.touch_student(conn, STUDENT, "u", "Ученик")
    conn.execute("UPDATE students SET status = 'paid', paid_at = ?, paid_until = ?, warned_at = NULL "
                 "WHERE user_id = ?", (time.time(), time.time() + days_left * DAY, STUDENT))
    conn.commit()


async def test_payment_gives_thirty_days(stand):
    dispatcher, bot, tg, conn = stand
    ready_to_sell(conn)
    await feed(dispatcher, bot, text("/start"), press("paid"), photo(), press(f"ok:{STUDENT}", user_id=ADMIN))
    left = db.get_student(conn, STUDENT)["paid_until"] - time.time()
    assert 29.9 * DAY < left <= 30 * DAY
    assert any("Доступ до" in t for t in tg.texts_to(STUDENT))


async def test_renewal_adds_month_to_remaining_days_without_new_link(stand):
    dispatcher, bot, tg, conn = stand
    ready_to_sell(conn)
    active_student(conn, days_left=2)
    await feed(dispatcher, bot, text("/start"))
    buttons = [b.callback_data for row in tg.of(SendMessage)[-1].reply_markup.inline_keyboard for b in row]
    assert "m:sub" in buttons and "m:buy" in buttons and "link" in buttons

    await feed(dispatcher, bot, press("m:buy"))
    assert "Продление" in tg.of(EditMessageText)[-1].text
    await feed(dispatcher, bot, press("paid"))
    assert db.status_of(conn, STUDENT) == "renew_waiting"
    await feed(dispatcher, bot, photo())
    assert db.status_of(conn, STUDENT) == "renew_pending"
    card = [m for m in tg.of(SendMessage) if m.chat_id == ADMIN][-1]
    assert "Продление" in card.text

    await feed(dispatcher, bot, press(f"ok:{STUDENT}", user_id=ADMIN, html=card.text))
    left = db.get_student(conn, STUDENT)["paid_until"] - time.time()
    assert 31.9 * DAY < left <= 32 * DAY          # 2 оставшихся дня + 30
    assert db.status_of(conn, STUDENT) == "paid"
    assert not tg.of(CreateChatInviteLink)        # уже в канале — ссылка не нужна
    assert any("продлён" in t for t in tg.texts_to(STUDENT))


async def test_rejected_renewal_keeps_current_access(stand):
    dispatcher, bot, tg, conn = stand
    ready_to_sell(conn)
    active_student(conn, days_left=5)
    until = db.get_student(conn, STUDENT)["paid_until"]
    await feed(dispatcher, bot, press("paid"), photo(), press(f"no:{STUDENT}", user_id=ADMIN))
    assert db.status_of(conn, STUDENT) == "paid"
    assert db.get_student(conn, STUDENT)["paid_until"] == until


async def test_warning_three_days_before_end_only_once(stand):
    dispatcher, bot, tg, conn = stand
    ready_to_sell(conn)
    config = dispatcher["config"]
    active_student(conn, days_left=10)
    await subscriptions.check(bot, conn, config)
    assert not tg.texts_to(STUDENT)

    active_student(conn, days_left=2.5)
    await subscriptions.check(bot, conn, config)
    warnings = [t for t in tg.texts_to(STUDENT) if "заканчивается" in t]
    assert len(warnings) == 1
    await subscriptions.check(bot, conn, config)
    assert len([t for t in tg.texts_to(STUDENT) if "заканчивается" in t]) == 1
    assert db.status_of(conn, STUDENT) == "paid"


async def test_not_renewed_student_is_removed_from_channel(stand):
    dispatcher, bot, tg, conn = stand
    ready_to_sell(conn)
    active_student(conn, days_left=0.5)
    until = db.get_student(conn, STUDENT)["paid_until"]
    await subscriptions.check(bot, conn, dispatcher["config"], now=until + 60)
    assert db.status_of(conn, STUDENT) == "expired"
    ban = [m for m in tg.sent if type(m).__name__ == "BanChatMember"]
    assert ban and ban[0].user_id == STUDENT and ban[0].chat_id == CHANNEL
    assert [m for m in tg.sent if type(m).__name__ == "UnbanChatMember"]
    assert content.EXPIRED in tg.texts_to(STUDENT)
    assert any("закончилась" in t for t in tg.texts_to(ADMIN))

    # вернулся и оплатил снова — новая ссылка и новый месяц
    await feed(dispatcher, bot, press("paid"), photo(), press(f"ok:{STUDENT}", user_id=ADMIN))
    assert db.status_of(conn, STUDENT) == "paid"
    assert tg.of(CreateChatInviteLink)


async def test_renewal_on_review_is_not_removed(stand):
    dispatcher, bot, tg, conn = stand
    ready_to_sell(conn)
    active_student(conn, days_left=1)
    await feed(dispatcher, bot, press("paid"), photo())
    until = db.get_student(conn, STUDENT)["paid_until"]
    await subscriptions.check(bot, conn, dispatcher["config"], now=until + 60)
    assert db.status_of(conn, STUDENT) == "renew_pending"   # ждём решения админа
    assert not [m for m in tg.sent if type(m).__name__ == "BanChatMember"]


def test_rules_are_visible_before_paying():
    rules = content.honest("каждые 2 дня", 2, False)
    assert "30 дней" in rules and "3 дня" in rules and "не продлевайте" in rules
    assert "не возвращаются" in content.buy("300", "Карта")
    assert any("Сколько длится доступ" in q for q, _ in content.FAQ)


async def test_new_link_for_paid_student(stand):
    dispatcher, bot, tg, conn = stand
    ready_to_sell(conn)
    active_student(conn)

    tg.member_status = "member"
    await feed(dispatcher, bot, press("link"))
    assert tg.of(AnswerCallbackQuery)[-1].text == content.ALREADY_IN_CHANNEL

    tg.member_status = "left"
    await feed(dispatcher, bot, press("link"))
    assert len(tg.of(CreateChatInviteLink)) == 1

    await feed(dispatcher, bot, press("link"))  # сразу ещё раз — рано
    assert tg.of(AnswerCallbackQuery)[-1].text == content.LINK_TOO_OFTEN
    assert len(tg.of(CreateChatInviteLink)) == 1


async def test_unpaid_student_gets_no_link(stand):
    dispatcher, bot, tg, conn = stand
    ready_to_sell(conn)
    await feed(dispatcher, bot, text("/start"), press("link"))
    assert not tg.of(CreateChatInviteLink)


async def test_admin_warned_when_someone_else_uses_link(stand):
    dispatcher, bot, tg, conn = stand
    ready_to_sell(conn)
    link = ChatInviteLink(invite_link="https://t.me/+once", creator=User(id=42, is_bot=True, first_name="b"),
                          creates_join_request=False, is_primary=False, is_revoked=False, name=f"id{STUDENT}")

    def joined(user_id):
        u = _user(user_id)
        return Update(update_id=next(_ids), chat_member=ChatMemberUpdated(
            chat=Chat(id=CHANNEL, type="channel"), from_user=u, date=datetime.now(),
            old_chat_member=ChatMemberLeft(user=u), new_chat_member=ChatMemberMember(user=u), invite_link=link))

    await feed(dispatcher, bot, joined(STUDENT))
    assert not tg.texts_to(ADMIN)
    await feed(dispatcher, bot, joined(OTHER))
    assert any(str(OTHER) in t and "другой человек" in t for t in tg.texts_to(ADMIN))
