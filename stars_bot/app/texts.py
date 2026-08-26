"""Все тексты бота в одном месте — правь тут, чтобы поменять стиль/язык."""
from __future__ import annotations

from app.config import settings


def money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + f" {settings.currency}"


START = (
    "👋 <b>Привет, {name}!</b>\n\n"
    "Здесь можно купить <b>Telegram Stars</b> ⭐ и <b>Telegram Premium</b> 💎 "
    "на любой аккаунт.\n\n"
    "• Выдача сразу после подтверждения оплаты\n"
    "• Нужен только @username получателя\n"
    "• Вход в чужой аккаунт и коды <b>не требуются</b>\n\n"
    "Выбери, что нужно 👇"
)

MENU_PROMPT = "Главное меню. Выбери раздел 👇"

CHOOSE_STARS = "⭐ <b>Telegram Stars</b>\n\nВыбери пакет:"
CHOOSE_PREMIUM = "💎 <b>Telegram Premium</b>\n\nВыбери срок подписки:"

ASK_RECIPIENT = (
    "{title} — {price}\n\n"
    "Отправь <b>@username</b> получателя.\n\n"
    "❗️ У аккаунта должен быть публичный юзернейм. "
    "Проверь его внимательно — после выдачи вернуть звёзды нельзя."
)

BAD_USERNAME = (
    "❌ Не похоже на юзернейм.\n\n"
    "Формат: <code>@username</code> — от 5 до 32 символов, "
    "латиница, цифры и подчёркивание."
)

UNKNOWN_RECIPIENT = (
    "❌ Fragment не нашёл получателя <b>@{username}</b>.\n\n"
    "Убедись, что юзернейм публичный и написан без опечаток, и пришли ещё раз."
)

CONFIRM_ORDER = (
    "🧾 <b>Проверь заказ</b>\n\n"
    "Товар: <b>{title}</b>\n"
    "Получатель: <b>@{recipient}</b>\n"
    "К оплате: <b>{price}</b>\n\n"
    "Всё верно?"
)

PAYMENT_INSTRUCTIONS = (
    "🧾 <b>Заказ №{order_id}</b>\n\n"
    "Товар: <b>{title}</b>\n"
    "Получатель: <b>@{recipient}</b>\n"
    "Сумма: <b>{price}</b>\n\n"
    "💳 <b>Переведи точную сумму на карту:</b>\n"
    "<code>{card}</code>\n"
    "{holder}{bank}\n\n"
    "После перевода пришли <b>скриншот чека</b> прямо в этот чат.\n"
    "Как проверю оплату — звёзды уйдут получателю автоматически."
)

RECEIPT_ACCEPTED = (
    "✅ Чек получен, заказ <b>№{order_id}</b> отправлен на проверку.\n\n"
    "Обычно занимает несколько минут. Я напишу, как только всё будет готово."
)

NEED_PHOTO = (
    "📸 Пришли именно <b>фото или файл</b> чека — так я смогу проверить оплату."
)

ORDER_DELIVERED = (
    "🎉 <b>Заказ №{order_id} выполнен!</b>\n\n"
    "{title} → <b>@{recipient}</b>\n\n"
    "Спасибо за покупку! Если что-то не пришло — напиши {support}."
)

ORDER_REJECTED = (
    "❌ <b>Заказ №{order_id} отклонён.</b>\n\n"
    "Причина: {reason}\n\n"
    "Если это ошибка — напиши {support}."
)

ORDER_FAILED_USER = (
    "⚠️ <b>Заказ №{order_id}: оплата принята, но выдача не прошла.</b>\n\n"
    "Я уже разбираюсь — деньги не потеряны. Напиши {support}, если нужен возврат."
)

ORDER_CANCELLED = "🚫 Заказ №{order_id} отменён."

NO_ORDERS = "У тебя пока нет заказов."

HELP = (
    "❓ <b>Как это работает</b>\n\n"
    "1️⃣ Выбираешь пакет звёзд или срок Premium\n"
    "2️⃣ Присылаешь @username получателя\n"
    "3️⃣ Переводишь сумму на карту и кидаешь чек\n"
    "4️⃣ После проверки оплаты выдача происходит автоматически\n\n"
    "🔒 Пароль, код из SMS и доступ к аккаунту <b>никогда</b> не нужны. "
    "Если кто-то их просит — это мошенник.\n\n"
    "По любым вопросам: {support}"
)

BANNED = "🚫 Доступ к боту закрыт."

# ---------------------------------------------------------------- админка

ADMIN_NEW_ORDER = (
    "🔔 <b>Новый заказ №{order_id}</b>\n\n"
    "Товар: <b>{title}</b>\n"
    "Получатель: <b>@{recipient}</b>\n"
    "Сумма: <b>{price}</b>\n"
    "Покупатель: {buyer} (<code>{user_id}</code>)"
)

ADMIN_APPROVED = "✅ Заказ №{order_id} подтверждён, выдаю…"
ADMIN_DELIVERED = "✅ Заказ №{order_id} выдан. Fragment ID: <code>{fragment_id}</code>"
ADMIN_FAILED = "⚠️ Заказ №{order_id}: выдача не удалась.\n\n<code>{error}</code>"
ADMIN_REJECTED = "❌ Заказ №{order_id} отклонён."
ADMIN_ALREADY_HANDLED = "Этот заказ уже обработан."
ADMIN_ONLY = "Команда только для админов."

ADMIN_HELP = (
    "🛠 <b>Админ-команды</b>\n\n"
    "/orders — последние заказы\n"
    "/pending — заказы на проверке\n"
    "/stats — статистика\n"
    "/balance — баланс Fragment\n"
    "/retry &lt;id&gt; — повторить выдачу упавшего заказа\n"
    "/ban &lt;user_id&gt; · /unban &lt;user_id&gt;"
)


def support() -> str:
    return f"@{settings.support_username}" if settings.support_username else "администратору"
