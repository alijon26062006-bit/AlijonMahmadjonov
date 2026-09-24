"""Бот админки: кнопки выполняют действия, чужие чаты игнорируются."""

from conftest import balance

from donatix import accounts, payments
from donatix.tgbot import AdminBot, payment_event, summary, user_event


class FakeApi:
    def __init__(self):
        self.calls = []

    def __call__(self, method, **payload):
        self.calls.append((method, payload))
        return []


def _bot(config):
    config.alert_telegram_chat_id = "777"
    config.alert_telegram_token = "t"
    api = FakeApi()
    return AdminBot(config, api=api), api


def _press(bot, conn, data, chat="777"):
    bot.handle(conn, {"update_id": 1, "callback_query": {
        "id": "cb", "data": data, "message": {"message_id": 5, "chat": {"id": int(chat)}, "text": "…"}}})


def test_buttons_confirm_payment_and_approve_user(config, conn):
    config.pay_methods = {"alif": "Алиф: +992 …"}
    bot, api = _bot(config)
    uid = accounts.create_user(conn, email="n@example.com", login="newbie", password="password123", status="pending")
    text, buttons = user_event(conn, uid)
    assert "newbie" in text and buttons[0][0][1] == f"user:ok:{uid}"
    _press(bot, conn, f"user:ok:{uid}")
    assert accounts.get_user(conn, uid)["status"] == "active"

    pid = payments.create(conn, config, accounts.get_user(conn, uid), "alif", "20")
    text, buttons = payment_event(conn, pid)
    assert "218.00 TJS" in text
    _press(bot, conn, f"pay:ok:{pid}")
    _press(bot, conn, f"pay:ok:{pid}")  # повторное нажатие — без второго зачисления
    assert balance(conn, uid) == 200_000
    answers = [p["text"] for m, p in api.calls if m == "answerCallbackQuery"]
    assert answers[-2:] == ["Зачислено, клиент получил уведомление", "Заявка уже обработана"]


def test_foreign_chat_is_ignored(config, conn):
    bot, api = _bot(config)
    uid = accounts.create_user(conn, email="x@example.com", login="xuser", password="password123", status="pending")
    _press(bot, conn, f"user:ok:{uid}", chat="999")
    assert accounts.get_user(conn, uid)["status"] == "pending"
    bot.handle(conn, {"update_id": 2, "message": {"chat": {"id": 999}, "text": "/stats"}})
    assert not [c for c in api.calls if c[0] == "sendMessage"]


def test_commands(config, conn):
    bot, api = _bot(config)
    bot.handle(conn, {"update_id": 3, "message": {"chat": {"id": 777}, "text": "/stats"}})
    assert "Сводка" in api.calls[-1][1]["text"]
    bot.handle(conn, {"update_id": 4, "message": {"chat": {"id": 777}, "text": "💳 Заявки"}})
    assert api.calls[-1][1]["text"] == "Заявок на пополнение нет."
    assert "Проблемных заказов" in summary(conn)
