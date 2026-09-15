"""Все тексты бота.

Значки не пишутся напрямую, а вставляются токеном [[stars]] — подстановка
идёт при обращении к тексту, поэтому смена значка в панели видна сразу.

Доступ через texts.ИМЯ работает как обычно: модульный __getattr__ отдаёт
шаблон уже с подставленными значками.
"""
from __future__ import annotations

from app.config import settings
from app.emoji import substitute
from app.money import fmt

LINE = "━━━━━━━━━━━━━━━━━━━━"


def support() -> str:
    return f"@{settings.support_username}" if settings.support_username else "поддержку"


_RAW: dict[str, str] = {}

# ═══════════════════════════════════════════════════════ главное меню

_RAW["MENU"] = (
    "<b>Добро пожаловать!</b>\n"
    "<blockquote>Здесь можно купить Telegram Stars и Telegram Premium "
    "на любой аккаунт — быстро и без входа в него.</blockquote>\n\n"
    "[[money]] Ваш баланс: <b>{balance}</b>\n\n"
    "<i>Выберите раздел ниже</i> [[point]]"
)

# ═════════════════════════════════════════════════════════════ звёзды

_RAW["STARS_ENTRY"] = (
    "[[stars]] <b>Telegram Stars</b>\n"
    f"<code>{LINE}</code>\n\n"
    "[[price]] Цена: <b>{rate}</b> за звезду\n\n"
    "<blockquote>Звёзды придут на любой аккаунт с публичным юзернеймом. "
    "Пароль и код из SMS не нужны никогда.</blockquote>\n\n"
    "<i>Выберите набор или задайте своё количество</i> [[point]]"
)

_RAW["STARS_ASK_QUANTITY"] = (
    "[[stars]] <b>Сколько звёзд?</b>\n"
    f"<code>{LINE}</code>\n\n"
    "[[price]] Цена: <b>{rate}</b> за штуку\n"
    "[[money]] Баланс: <b>{balance}</b> — хватит на <b>{affordable}</b> ⭐\n\n"
    "<blockquote>Минимум — <b>{min_stars}</b>, максимум — <b>{max_stars}</b> "
    "за один заказ.</blockquote>\n\n"
    "[[search]] <i>Введите количество числом:</i>"
)

_RAW["STARS_BAD_QUANTITY"] = (
    "[[fail]] Введите <b>целое число</b> от <code>{min_stars}</code> "
    "до <code>{max_stars}</code>."
)

_RAW["STARS_NOT_ENOUGH"] = (
    "[[fail]] <b>Не хватает средств</b>\n"
    f"<code>{LINE}</code>\n\n"
    "├ Нужно: <b>{need}</b>\n"
    "├ Есть: <b>{balance}</b>\n"
    "└ Не хватает: <b>{missing}</b>\n\n"
    "<blockquote>Пополните баланс — и заказ пройдёт сразу.</blockquote>"
)

# ═══════════════════════════════════════════════════════════════ игры

_RAW["GAMES_ENTRY"] = (
    "[[game]][[pubg]] <b>Пополнение игр</b>\n"
    f"<code>{LINE}</code>\n\n"
    "<blockquote>Пополнение приходит прямо на игровой аккаунт. "
    "Нужен только <b>ID игрока</b> — пароль от аккаунта не спрашиваем "
    "никогда.</blockquote>\n\n"
    "<i>Выберите игру</i> [[point]]"
)

_RAW["GAME_REGION"] = (
    "[[game]] <b>{title}</b>\n"
    f"<code>{LINE}</code>\n\n"
    "[[point]] <b>Выберите регион аккаунта</b>\n\n"
    "<blockquote>Регион — это сервер, на котором вы играете. Он виден "
    "в профиле игры рядом с ником и ID.\n\n"
    "Регион важен: на чужом сервере ваш ID просто не найдётся, и "
    "пополнение не дойдёт.</blockquote>"
)

_RAW["GAME_PACKS"] = (
    "[[game]] <b>{title}</b>{region}\n"
    f"<code>{LINE}</code>\n\n"
    "<blockquote>Выберите пакет — дальше спрошу ID игрока и покажу ник, "
    "чтобы вы убедились, что это ваш аккаунт.</blockquote>"
)

_RAW["GAME_ASK_ID"] = (
    "[[game]] <b>{title}</b>{region} — {pack}\n"
    f"<code>{LINE}</code>\n\n"
    "[[profile]] <b>ID игрока</b>\n\n"
    "<blockquote>Пришлите <b>числовой ID</b> вашего аккаунта. Он виден "
    "в профиле игры рядом с ником.</blockquote>"
)

_RAW["GAME_ASK_TWO"] = (
    "[[game]] <b>{title}</b>{region} — {pack}\n"
    f"<code>{LINE}</code>\n\n"
    "[[profile]] <b>{first} и {second}</b>\n\n"
    "<blockquote>Пришлите одним сообщением через пробел:\n"
    "<code>{example}</code>\n\n"
    "В профиле игры они стоят рядом: сначала ID, потом сервер "
    "в скобках.</blockquote>"
)

_RAW["GAME_TWO_FORMAT"] = (
    "[[fail]] <b>Нужны два числа</b>\n\n"
    "<blockquote>{first} и {second} — одним сообщением через пробел:\n"
    "<code>{example}</code>\n\n"
    "В профиле игры они написаны рядом, сервер обычно в "
    "скобках.</blockquote>"
)

_RAW["GAME_CHECKING"] = "[[search]] <i>Проверяю ID</i> <code>{player}</code>…"

_RAW["GAME_CONFIRM"] = (
    "[[search]] <b>Проверьте аккаунт</b>\n"
    f"<code>{LINE}</code>\n\n"
    "├ Игрок: <b>{name}</b>\n"
    "├ ID: <code>{player}</code>\n"
    "├ Пакет: <b>{pack}</b>\n"
    "├ К списанию: <b>{price}</b>\n"
    "└ Останется: <b>{rest}</b>\n\n"
    "<blockquote>[[warn]] Пополнение уйдёт на этот ID, вернуть его будет "
    "нельзя. Убедитесь, что аккаунт ваш.</blockquote>"
)

_RAW["GAME_NO_NAME"] = (
    "[[search]] <b>ID принят</b>\n"
    f"<code>{LINE}</code>\n\n"
    "├ ID: <code>{player}</code>\n"
    "├ Пакет: <b>{pack}</b>\n"
    "├ К списанию: <b>{price}</b>\n"
    "└ Останется: <b>{rest}</b>\n\n"
    "<blockquote>[[warn]] Ник показать не удалось — проверьте ID сами, "
    "особенно каждую цифру. Пополнение уйдёт на этот ID, и вернуть его "
    "будет нельзя.</blockquote>"
)

_RAW["GAME_ID_FORMAT"] = (
    "[[fail]] <b>Это не похоже на ID</b>\n\n"
    "<blockquote>ID игрока — только цифры, от 5 до 20 знаков. Он виден "
    "в профиле игры рядом с ником.\n\nПришлите его ещё раз.</blockquote>"
)

_RAW["GAME_WRONG_REGION"] = (
    "[[search]] <b>Нашёл ваш аккаунт в другом регионе</b>\n"
    f"<code>{LINE}</code>\n\n"
    "├ ID: <code>{player}</code>\n"
    "├ Игрок: <b>{name}</b>\n"
    "└ Регион: <b>{region}</b>\n\n"
    "<blockquote>В выбранном регионе такого ID нет, а здесь он есть. "
    "Нажмите нужный регион — и выберите пакет заново.</blockquote>"
)

_RAW["GAME_UNVERIFIED"] = (
    "[[warn]] <b>ID не подтвердился</b>\n"
    f"<code>{LINE}</code>\n\n"
    "├ ID: <code>{player}</code>\n"
    "├ Пакет: <b>{pack}</b>\n"
    "├ К списанию: <b>{price}</b>\n"
    "└ Останется: <b>{rest}</b>\n\n"
    "<blockquote>Проверка не нашла этот ID. Это не всегда ошибка: "
    "для части серверов проверка вообще не работает.\n\n"
    "Уверены в ID — покупайте. Не уверены — смените регион или "
    "пришлите ID ещё раз.\n\n"
    "[[warn]] Пополнение уйдёт на этот ID, вернуть его будет "
    "нельзя.</blockquote>"
)

_RAW["GAME_ACCEPTED"] = (
    "[[ok]] <b>Заказ №{order_id} принят</b>\n"
    f"<code>{LINE}</code>\n\n"
    "├ Пакет: <b>{pack}</b>\n"
    "├ ID: <code>{player}</code>\n"
    "└ Списано: <b>{price}</b>\n\n"
    "<blockquote>[[wait]] Пополнение уже идёт — обычно меньше минуты. "
    "Напишу, как только дойдёт.</blockquote>"
)

_RAW["GAME_DELIVERED"] = (
    "[[party]] <b>Заказ №{order_id} выполнен!</b>\n"
    f"<code>{LINE}</code>\n\n"
    "├ Пакет: <b>{pack}</b>\n"
    "├ ID: <code>{player}</code>\n"
    "└ Списано: <b>{price}</b>\n\n"
    "<blockquote>Проверьте игру. Если пополнения нет — напишите "
    "в поддержку.</blockquote>"
)

# ══════════════════════════════════════════════════════════════ steam

_RAW["STEAM_ENTRY"] = (
    "[[steam]] <b>Пополнение Steam</b>\n"
    f"<code>{LINE}</code>\n\n"
    "<blockquote>Деньги придут на кошелёк Steam. Нужен только <b>логин</b> — "
    "пароль и код Steam Guard не спрашиваем никогда.</blockquote>\n\n"
    "<i>Выберите сумму</i> [[point]]"
)

_RAW["STEAM_ASK_LOGIN"] = (
    "[[steam]] <b>{amount} {currency}</b> — <b>{price}</b>\n"
    f"<code>{LINE}</code>\n\n"
    "[[profile]] <b>Логин Steam</b>\n\n"
    "<blockquote>Пришлите <b>логин аккаунта</b> — тот, которым вы входите "
    "в Steam. Это не ник в профиле и не почта.</blockquote>"
)

_RAW["STEAM_CHECKING"] = "[[search]] <i>Проверяю аккаунт</i> <code>{login}</code>…"

_RAW["STEAM_CONFIRM"] = (
    "[[search]] <b>Проверьте аккаунт</b>\n"
    f"<code>{LINE}</code>\n\n"
    "├ Аккаунт: <b>{name}</b>\n"
    "├ Логин: <code>{login}</code>\n"
    "├ Сумма: <b>{amount} {currency}</b>\n"
    "├ К списанию: <b>{price}</b>\n"
    "└ Останется: <b>{rest}</b>\n\n"
    "<blockquote>[[warn]] Деньги уйдут на этот аккаунт и вернуть их будет "
    "нельзя. Убедитесь, что логин верный.</blockquote>"
)

_RAW["STEAM_BAD_LOGIN"] = (
    "[[fail]] <b>Такого аккаунта нет</b>\n\n"
    "<blockquote>Steam не знает логин <code>{login}</code>. Проверьте "
    "написание и пришлите ещё раз.\n\nНужен именно логин для входа, "
    "а не ник в профиле.</blockquote>"
)

_RAW["STEAM_NO_CHECK"] = (
    "[[warn]] <b>Не удалось проверить аккаунт</b>\n\n"
    "<blockquote>Steam сейчас не отвечает. Попробуйте через пару минут — "
    "лучше подождать, чем отправить деньги не туда.</blockquote>"
)

_RAW["STEAM_DELIVERED"] = (
    "[[party]] <b>Заказ №{order_id} выполнен!</b>\n"
    f"<code>{LINE}</code>\n\n"
    "├ Steam: <code>{login}</code>\n"
    "├ Зачислено: <b>{amount} {currency}</b>\n"
    "└ Списано: <b>{price}</b>\n\n"
    "<blockquote>Проверьте кошелёк Steam. Если денег нет — напишите "
    "в поддержку.</blockquote>"
)

# ════════════════════════════════════════════════════════════ premium

_RAW["PREMIUM_ENTRY"] = (
    "[[premium]] <b>Telegram Premium</b>\n"
    f"<code>{LINE}</code>\n\n"
    "<blockquote>Подписка оформляется на аккаунт с публичным юзернеймом. "
    "Доступ к аккаунту не нужен.</blockquote>\n\n"
    "<i>Выберите срок</i> [[point]]"
)

# ══════════════════════════════════════════════════════════ получатель

_RAW["ASK_RECIPIENT"] = (
    "<b>{title}</b> — <b>{price}</b>\n"
    f"<code>{LINE}</code>\n\n"
    "[[profile]] <b>Кому отправляем?</b>\n\n"
    "<blockquote>Нажмите «Себе», если покупаете для своего аккаунта — "
    "юзернейм подставится сам и ошибиться будет невозможно.</blockquote>\n\n"
    "<i>Или пришлите</i> <code>@username</code> <i>получателя.</i>"
)

_RAW["NO_OWN_USERNAME"] = (
    "[[fail]] <b>У вас не установлен юзернейм</b>\n"
    f"<code>{LINE}</code>\n\n"
    "<blockquote>Звёзды отправляются только на аккаунты с публичным "
    "юзернеймом — без него аккаунт не найти.</blockquote>\n\n"
    "<b>Как включить:</b>\n"
    "├ Настройки Telegram\n"
    "├ Мой профиль\n"
    "└ <b>Имя пользователя</b> → придумайте свободное\n\n"
    "<i>Потом вернитесь и нажмите «Себе» ещё раз.</i>"
)

_RAW["CHECKING_RECIPIENT"] = "[[search]] <i>Проверяю аккаунт</i> <code>@{username}</code>…"

_RAW["BAD_USERNAME"] = (
    "[[fail]] <b>Это не похоже на юзернейм</b>\n\n"
    "<blockquote>Нужен формат <code>@username</code>: от 5 до 32 символов, "
    "латиница, цифры и подчёркивание.</blockquote>"
)

_RAW["UNKNOWN_RECIPIENT"] = (
    "[[fail]] <b>Аккаунт @{username} не найден</b>\n\n"
    "<blockquote>Проверьте, что юзернейм публичный и написан без опечаток.</blockquote>"
)

_RAW["CONFIRM_RECIPIENT"] = (
    "[[search]] <b>Проверьте получателя</b>\n"
    f"<code>{LINE}</code>\n\n"
    "├ Аккаунт: <b>{name}</b>\n"
    "└ Юзернейм: <code>@{username}</code>\n\n"
    "{who}\n\n"
    "<blockquote>[[warn]] <b>{title}</b> уйдут именно на этот аккаунт. "
    "После отправки вернуть их нельзя.</blockquote>\n\n"
    "<i>Всё верно?</i>"
)

_RAW["CONFIRM_RECIPIENT_UNVERIFIED"] = (
    "[[search]] <b>Проверьте получателя</b>\n"
    f"<code>{LINE}</code>\n\n"
    "└ Юзернейм: <code>@{username}</code>\n\n"
    "{who}\n\n"
    "<blockquote>[[warn]] Имя аккаунта проверить нельзя — сервис выдачи "
    "его не сообщает. Откройте <code>t.me/{username}</code> и убедитесь, "
    "что это нужный человек.\n\n"
    "<b>{title}</b> уйдут именно на этот юзернейм, вернуть их нельзя."
    "</blockquote>\n\n"
    "<i>Юзернейм верный?</i>"
)

_RAW["RECIPIENT_IS_YOU"] = "[[ok]] <b>Это ваш аккаунт.</b>"
_RAW["RECIPIENT_IS_OTHER"] = "[[warn]] Это <b>чужой</b> аккаунт — проверьте внимательно."

_RAW["CONFIRM"] = (
    "[[receipt]] <b>Подтверждение заказа</b>\n"
    f"<code>{LINE}</code>\n\n"
    "├ Товар: <b>{title}</b>\n"
    "├ Получатель: <b>{name}</b> (<code>@{recipient}</code>)\n"
    "{discount}"
    "├ К списанию: <b>{price}</b>\n"
    "└ Останется: <b>{rest}</b>\n\n"
    "<blockquote>Нажимая «Оплатить», вы подтверждаете, что аккаунт указан "
    "верно.</blockquote>"
)

_RAW["CONFIRM_DISCOUNT"] = (
    "├ Цена: <s>{full}</s>\n"
    "├ Промокод <code>{code}</code>: <b>−{percent}%</b> (−{saved})\n"
)

_RAW["ORDER_PROMO_ASK"] = (
    "[[promo]] <b>Промокод на скидку</b>\n"
    f"<code>{LINE}</code>\n\n"
    "<blockquote>Введите код — пересчитаю стоимость заказа.</blockquote>"
)

_RAW["ORDER_PROMO_OK"] = (
    "[[party]] <b>Промокод {code} применён</b>\n\n"
    "├ Скидка: <b>{percent}%</b>\n"
    "└ Экономия: <b>{saved}</b>"
)

_RAW["PROCESSING"] = "[[wait]] <i>Оплачено. Отправляю {title} на</i> <code>@{recipient}</code>…"

_RAW["PROCESSING_SLOW"] = (
    "[[ok]] <b>Заказ принят и оплачен</b>\n"
    f"<code>{LINE}</code>\n\n"
    "├ Товар: <b>{title}</b>\n"
    "└ Получатель: <code>@{recipient}</code>\n\n"
    "<blockquote>[[wait]] Выдача занимает несколько минут. Я напишу, как "
    "только всё придёт — чат можно закрыть.</blockquote>"
)

_RAW["DELIVERED"] = (
    "[[party]] <b>Заказ №{order_id} выполнен!</b>\n"
    f"<code>{LINE}</code>\n\n"
    "├ Товар: <b>{title}</b>\n"
    "├ Получатель: <code>@{recipient}</code>\n"
    "└ Списано: <b>{price}</b>\n\n"
    "<blockquote>Спасибо за покупку! Если что-то не пришло — "
    "напишите в поддержку.</blockquote>"
)

_RAW["REVIEW_ASK"] = (
    "[[reviews]] <b>Как всё прошло?</b>\n"
    f"<code>{LINE}</code>\n\n"
    "<blockquote>Поставьте оценку заказу <b>№{order_id}</b> — это займёт "
    "секунду и поможет другим покупателям.</blockquote>"
)

_RAW["REVIEW_ASK_OLD"] = (
    "[[reviews]] <b>Вы покупали у нас — как всё прошло?</b>\n"
    f"<code>{LINE}</code>\n\n"
    "├ Заказ: <b>№{order_id}</b>\n"
    "└ Товар: <b>{title}</b>\n\n"
    "<blockquote>Поставьте оценку — это займёт секунду и поможет другим "
    "покупателям выбрать нас.</blockquote>"
)

_RAW["REVIEW_ASK_TEXT"] = (
    "[[reviews]] <b>Оценка {stars}</b>\n"
    f"<code>{LINE}</code>\n\n"
    "<blockquote>Напишите пару слов о покупке — мы публикуем отзывы в нашем "
    "канале.\n\nВаше имя будет видно под отзывом.</blockquote>"
)

_RAW["REVIEW_SENT"] = (
    "[[party]] <b>Спасибо за отзыв!</b>\n\n"
    "<blockquote>Скоро он появится в нашем канале.</blockquote>"
)

_RAW["REVIEW_ALREADY"] = (
    "[[warn]] <b>Отзыв на этот заказ уже есть.</b>\n\n"
    "<blockquote>Один заказ — один отзыв.</blockquote>"
)

#: Как отзыв выглядит в канале.
_RAW["REVIEW_POST"] = (
    "{stars}\n"
    "<b>Отзыв о покупке</b>\n"
    f"<code>{LINE}</code>\n\n"
    "<blockquote>{text}</blockquote>\n\n"
    "├ Товар: <b>{title}</b>\n"
    "└ Покупатель: <b>{author}</b>"
)

_RAW["REVIEW_POST_SHORT"] = (
    "{stars}\n"
    "<b>Отзыв о покупке</b>\n"
    f"<code>{LINE}</code>\n\n"
    "├ Товар: <b>{title}</b>\n"
    "└ Покупатель: <b>{author}</b>"
)

_RAW["ADMIN_REVIEW"] = (
    "[[reviews]] <b>Новый отзыв на проверку</b>\n"
    f"<code>{LINE}</code>\n\n"
    "├ Оценка: {stars} <b>({rating}/5)</b>\n"
    "├ Заказ: <b>№{order_id}</b> — {title}\n"
    "├ Никнейм: {username}\n"
    "├ Имя: <b>{name}</b>\n"
    "└ ID: <code>{user_id}</code> · <a href=\"tg://user?id={user_id}\">написать</a>\n\n"
    "<blockquote>{text}</blockquote>\n\n"
    "<i>Так отзыв подпишут в канале: {author}</i>"
)

_RAW["REFUNDED"] = (
    "[[refund]] <b>Заказ №{order_id} не выполнен</b>\n"
    f"<code>{LINE}</code>\n\n"
    "<blockquote>[[money]] <b>{price}</b> уже вернулись на ваш баланс — "
    "деньги не потеряны.</blockquote>\n\n"
    "<i>Попробуйте ещё раз чуть позже или напишите в {support}.</i>"
)

# ═══════════════════════════════════════════════════════════ пополнение

_RAW["DEPOSIT_METHODS"] = (
    "[[deposit]] <b>Пополнение баланса</b>\n"
    f"<code>{LINE}</code>\n\n"
    "<blockquote>Переведите нужную сумму по реквизитам и пришлите чек — "
    "баланс пополнится после проверки.</blockquote>\n\n"
    "<i>Выберите способ</i> [[point]]"
)

_RAW["DEPOSIT_ASK_AMOUNT"] = (
    "[[deposit]] <b>Перевод на карту</b>\n"
    f"<code>{LINE}</code>\n\n"
    "Минимальная сумма: <b>{min_amount}</b>\n\n"
    "[[search]] <i>Введите сумму в сомони — например</i> "
    "<code>150</code> <i>или</i> <code>150.50</code>:"
)

_RAW["DEPOSIT_BAD_AMOUNT"] = (
    "[[fail]] Введите сумму числом: <code>150</code> или <code>150.50</code>."
)

_RAW["DEPOSIT_TOO_SMALL"] = "[[fail]] Минимальная сумма пополнения — <b>{min_amount}</b>."

_RAW["DEPOSIT_REQUISITES"] = (
    "[[deposit]] <b>Переведите {amount}</b>\n"
    f"<code>{LINE}</code>\n\n"
    "<code>{card}</code>\n"
    "{holder}{bank}"
    "{extra}"
    "<blockquote>[[warn]] Сумма — <b>ровно {amount}</b>, до копейки.\n"
    "{dc_block}</blockquote>\n\n"
    "<i>[[ok]] Придут деньги — баланс пополнится сам</i>"
)

#: Приписка про код платежа. Он нужен, чтобы найти перевод в выписке,
#: даже если чек не придёт.
_RAW["DEPOSIT_DC_BLOCK"] = "Код платежа: <code>{reference}</code>"

_RAW["DEPOSIT_ASK_RECEIPT"] = (
    "📸 <b>Пришлите чек</b>\n"
    f"<code>{LINE}</code>\n\n"
    "Отправьте сюда скриншот чека на <b>{amount}</b> — одним "
    "сообщением.\n\n"
    "<blockquote>[[ok]] Как только чек придёт и банк подтвердит перевод, "
    "баланс пополнится <b>сам</b> — подтверждать вручную ничего не надо."
    "\n\nЧек нужен, чтобы мы точно знали, что этот перевод ваш: "
    "одну и ту же сумму в одну минуту могут отправить двое."
    "</blockquote>"
)

_RAW["DEPOSIT_NEED_PHOTO"] = (
    "📸 Если баланс не пополнился сам — пришлите <b>фото или скриншот</b> "
    "чека. По тексту оплату не проверить."
)

_RAW["DEPOSIT_SENT"] = (
    "[[ok]] <b>Чек получен — заявка №{deposit_id}</b>\n"
    f"<code>{LINE}</code>\n\n"
    "└ Сумма: <b>{amount}</b>\n\n"
    "<blockquote>[[wait]] Проверим вручную и пополним баланс. Я напишу, "
    "как только это произойдёт.</blockquote>"
)

_RAW["DEPOSIT_APPROVED"] = (
    "[[party]] <b>Баланс пополнен на {amount}!</b>\n\n"
    "[[money]] Текущий баланс: <b>{balance}</b>"
)

_RAW["DEPOSIT_REJECTED"] = (
    "[[fail]] <b>Пополнение №{deposit_id} отклонено</b>\n"
    f"<code>{LINE}</code>\n\n"
    "<blockquote>Оплата на {amount} не найдена. Если это ошибка — "
    "напишите в {support} и приложите чек.</blockquote>"
)

_RAW["DEPOSIT_SOON"] = (
    "🔧 Этот способ пока не подключён.\n\nСейчас доступен перевод на карту."
)

# ══════════════════════════════════════════════════════════════ профиль

_RAW["PROFILE"] = (
    "[[profile]] <b>Профиль</b>\n"
    f"<code>{LINE}</code>\n\n"
    "├ ID: <code>{user_id}</code>\n"
    "└ Username: {username}\n\n"
    "[[money]] <b>Финансы</b>\n"
    "├ Баланс: <b>{balance}</b>\n"
    "└ Всего пополнено: <b>{total_deposit}</b>\n\n"
    "📦 <b>Заказы</b>\n"
    "├ Всего: <b>{total}</b>\n"
    "├ Выполнено: <b>{done}</b>\n"
    "├ В обработке: <b>{active}</b>\n"
    "├ Premium: <b>{premium}</b> мес. <i>(~{premium_spent})</i>\n"
    "└ Звёзд куплено: <b>{stars}</b> <i>(~{stars_spent})</i>\n\n"
    "📅 <i>С нами с {created}</i>"
)

_RAW["HISTORY_EMPTY"] = (
    "[[history]] <b>История покупок</b>\n"
    f"<code>{LINE}</code>\n\n"
    "<blockquote>Здесь появятся ваши заказы: что купили, кому и чем "
    "закончилось.</blockquote>\n\n"
    "<i>Пока пусто.</i>"
)

_RAW["HISTORY"] = (
    "[[history]] <b>История покупок</b>\n"
    f"<code>{LINE}</code>\n\n"
    "{summary}\n\n"
    "{items}"
)

_RAW["HISTORY_SUMMARY"] = (
    "<blockquote>[[ok]] Выполнено: <b>{done}</b>   "
    "[[refund]] Возвращено: <b>{refunded}</b>\n"
    "[[money]] Потрачено всего: <b>{spent}</b></blockquote>"
)

# ═══════════════════════════════════════════════════════════ промокоды

_RAW["PROMO_ASK"] = (
    "[[promo]] <b>Промокод</b>\n\n"
    "<blockquote>Введите код — сумма зачислится на баланс сразу.</blockquote>"
)

_RAW["PROMO_OK"] = (
    "[[party]] <b>Промокод активирован!</b>\n\n"
    "├ Начислено: <b>{amount}</b>\n"
    "└ Баланс: <b>{balance}</b>"
)

# ════════════════════════════════════════════════════════════ рефералы

_RAW["REFERRAL"] = (
    "[[referral]] <b>Реферальная система</b>\n"
    f"<code>{LINE}</code>\n\n"
    "<blockquote>Приглашайте друзей и получайте <b>{percent}%</b> "
    "с каждого их пополнения — навсегда.</blockquote>\n\n"
    "├ Приглашено: <b>{ref_count}</b> чел.\n"
    "└ Заработано: <b>{ref_earned}</b>\n\n"
    "🔗 <b>Ваша ссылка</b>\n<code>{link}</code>\n\n"
    "<i>Нажмите на ссылку, чтобы скопировать.</i>"
)

_RAW["REFERRAL_BONUS"] = (
    "[[referral]] <b>+{amount}</b> за пополнение вашего реферала!\n\n"
    "[[money]] Баланс: <b>{balance}</b>"
)

# ═══════════════════════════════════════════════════════════ поддержка

_RAW["SUPPORT"] = (
    "[[support]] <b>Поддержка</b>\n"
    f"<code>{LINE}</code>\n\n"
    "📊 Активных обращений: <b>{open_tickets}</b>\n\n"
    "<blockquote>{notice}</blockquote>\n\n"
    "<i>Опишите проблему — отвечу в этом чате.</i>"
)

_RAW["SUPPORT_NOTICE_DEFAULT"] = (
    "Среднее время ответа — до 30 минут. Перед обращением загляните "
    "в раздел «Информация»: там ответы на частые вопросы."
)

_RAW["TICKET_ASK_SUBJECT"] = (
    "📝 <b>Новое обращение</b>\n\n"
    "<blockquote>Опишите проблему одним сообщением. Если вопрос по "
    "заказу — укажите его номер.</blockquote>"
)

_RAW["TICKET_CREATED"] = (
    "[[ok]] <b>Обращение №{ticket_id} создано</b>\n\n"
    "<blockquote>Ответ придёт в этот чат. Чтобы дописать — откройте "
    "раздел «Поддержка».</blockquote>"
)

_RAW["TICKET_ASK_REPLY"] = "✍️ <i>Напишите сообщение в обращение №{ticket_id}:</i>"
_RAW["TICKET_USER_REPLY_SENT"] = "[[ok]] Сообщение отправлено в обращение №{ticket_id}."
_RAW["TICKET_ADMIN_ANSWER"] = (
    "[[support]] <b>Ответ поддержки</b> <i>(обращение №{ticket_id})</i>\n"
    f"<code>{LINE}</code>\n\n"
    "<blockquote>{text}</blockquote>"
)
_RAW["TICKET_CLOSED_USER"] = (
    "[[ok]] Обращение №{ticket_id} закрыто.\n\n"
    "<i>Если вопрос остался — создайте новое.</i>"
)
_RAW["TICKET_LIMIT"] = "У вас уже есть открытое обращение. Дождитесь ответа по нему."

# ═════════════════════════════════════════════════════════ калькулятор

_RAW["CALC_ASK"] = (
    "[[calc]] <b>Калькулятор</b>\n"
    f"<code>{LINE}</code>\n\n"
    "[[price]] Курс: <b>{rate}</b> за звезду\n\n"
    "<blockquote>Отправьте <b>число</b> — посчитаю стоимость.\n"
    "Отправьте <b>сумму с буквой с</b> — посчитаю, сколько выйдет звёзд."
    "</blockquote>\n\n"
    "<i>Например:</i> <code>500</code> <i>или</i> <code>100с</code>"
)

_RAW["CALC_STARS"] = "[[stars]] <b>{stars}</b> звёзд = <b>{price}</b>"
_RAW["CALC_MONEY"] = "[[money]] На <b>{money}</b> можно купить <b>~{stars}</b> звёзд"
_RAW["CALC_BAD"] = (
    "[[fail]] Не понял. Отправьте число звёзд или сумму: <code>100с</code>"
)

# ══════════════════════════════════════════════════════════ информация

_RAW["INFO"] = (
    "[[info]] <b>Как это работает</b>\n"
    f"<code>{LINE}</code>\n\n"
    "<b>1️⃣</b> Пополняете баланс переводом на карту\n"
    "<b>2️⃣</b> Выбираете количество звёзд\n"
    "<b>3️⃣</b> Указываете <code>@username</code> получателя\n"
    "<b>4️⃣</b> Звёзды приходят\n\n"
    "<blockquote expandable><b>Частые вопросы</b>\n\n"
    "<b>Нужен ли доступ к аккаунту?</b>\n"
    "Нет. Пароль, код из SMS и вход в аккаунт не нужны <b>никогда</b>. "
    "Если кто-то их просит — это мошенник.\n\n"
    "<b>Можно на чужой аккаунт?</b>\n"
    "Да, достаточно публичного юзернейма.\n\n"
    "<b>Что если заказ не прошёл?</b>\n"
    "Деньги возвращаются на баланс автоматически.\n\n"
    "<b>Сколько ждать пополнение?</b>\n"
    "Обычно несколько минут после отправки чека.\n\n"
    "<b>Можно вернуть звёзды?</b>\n"
    "Нет. После отправки операция необратима — проверяйте получателя."
    "</blockquote>\n\n"
    "[[support]] Поддержка: {support}"
)

_RAW["TOP_CLIENTS"] = (
    "[[top]] <b>Топ клиентов</b>\n"
    f"<code>{LINE}</code>\n\n"
    "{items}\n\n"
    "<blockquote>Рейтинг по сумме {basis} за всё время.</blockquote>"
)
_RAW["TOP_EMPTY"] = (
    "[[top]] <b>Топ клиентов</b>\n\n"
    "<blockquote>Пока пусто — станьте первым!</blockquote>"
)

_RAW["BANNED"] = "[[block]] <b>Доступ к боту закрыт.</b>"
_RAW["SOON"] = "🔧 Раздел в разработке."

# ═════════════════════════════════════════════════════════════ админка

_RAW["ADMIN_NEW_DEPOSIT"] = (
    "🔔 <b>Пополнение №{deposit_id}</b>\n"
    f"<code>{LINE}</code>\n\n"
    "├ Сумма: <b>{amount}</b>\n"
    "├ Способ: {method}\n"
    "├ Код платежа: <code>{reference}</code>\n"
    "├ Покупатель: {buyer}\n"
    "└ ID: <code>{user_id}</code>"
)

_RAW["ADMIN_DEPOSIT_RECEIPT"] = (
    "[[ok]] <b>Чек к пополнению №{deposit_id}</b>\n"
    f"<code>{LINE}</code>\n\n"
    "├ Заявлено клиентом: <b>{amount}</b>\n"
    "├ Банк подтвердил: <b>{paid}</b>\n"
    "├ Код банка: <code>{code}</code>\n"
    "├ Отправитель: <code>{sender}</code>\n"
    "├ Покупатель: {buyer}\n"
    "└ ID: <code>{user_id}</code>\n\n"
    "<blockquote>Деньги уже зачислены автоматически — делать ничего не "
    "надо. Чек лежит здесь на случай спора.</blockquote>"
)

_RAW["ADMIN_NEW_TICKET"] = (
    "[[support]] <b>Обращение №{ticket_id}</b>\n"
    f"<code>{LINE}</code>\n\n"
    "├ От: {buyer} (<code>{user_id}</code>)\n"
    "└ Баланс: <b>{balance}</b>\n\n"
    "<blockquote>{subject}</blockquote>\n\n"
    "<i>Ответить:</i> <code>/answer {ticket_id} текст</code>"
)

_RAW["ADMIN_TICKET_REPLY"] = (
    "💬 <b>Ответ в обращении №{ticket_id}</b>\n"
    "От {buyer} (<code>{user_id}</code>)\n\n"
    "<blockquote>{text}</blockquote>"
)

_RAW["ADMIN_ORDER_DONE"] = (
    "[[ok]] <b>Заказ №{order_id}</b>\n"
    "{title} → <code>@{recipient}</code>\n"
    "<b>{price}</b> · покупатель <code>{user_id}</code>\n"
    "🔗 На платформе: <code>{external}</code>"
)

_RAW["ADMIN_ORDER_FAILED"] = (
    "[[warn]] <b>Заказ №{order_id} не прошёл</b>\n"
    f"<code>{LINE}</code>\n\n"
    "├ {title} → <code>@{recipient}</code>\n"
    "└ Покупатель: <code>{user_id}</code>\n\n"
    "<blockquote expandable>{error}</blockquote>"
)

_RAW["ADMIN_ALREADY_HANDLED"] = "Эта заявка уже обработана."
_RAW["ADMIN_DEPOSIT_OK"] = "[[ok]] Пополнение №{deposit_id} на {amount} зачислено."
_RAW["ADMIN_DEPOSIT_NO"] = "[[fail]] Пополнение №{deposit_id} отклонено."

_RAW["ADMIN_HELP"] = (
    "🛠 <b>Команды администратора</b>\n"
    f"<code>{LINE}</code>\n\n"
    "<b>Заявки</b>\n"
    "├ /pending — пополнения на проверке\n"
    "├ /tickets — открытые обращения\n"
    "├ /answer &lt;id&gt; &lt;текст&gt; — ответить\n"
    "└ /close &lt;id&gt; — закрыть обращение\n\n"
    "<b>Заказы и деньги</b>\n"
    "├ /stats — статистика\n"
    "├ /orders — последние заказы\n"
    "├ /retry &lt;id&gt; — повторить выдачу\n"
    "├ /done &lt;id&gt; · /refund &lt;id&gt; — закрыть или вернуть\n"    "├ /gorder &lt;id&gt; — статус игрового заказа у поставщика\n"    "├ /nick &lt;id&gt; — проверить ник у всех источников\n"
    "├ /give &lt;id&gt; &lt;сумма&gt; — начислить\n"
    "└ /take &lt;id&gt; &lt;сумма&gt; — списать\n\n"
    "<b>Прочее</b>\n"
    "├ /promo &lt;код&gt; &lt;сумма&gt; &lt;лимит&gt;\n"
    "├ /broadcast &lt;текст&gt; — рассылка\n"
    "├ /user &lt;id&gt; — карточка\n"
    "└ /ban &lt;id&gt; · /unban &lt;id&gt;"
)


def money_stats(data: dict) -> str:
    return substitute(
        "📊 <b>Статистика</b>\n"
        f"<code>{LINE}</code>\n\n"
        f"[[referral]] Пользователей: <b>{data['users']}</b>\n"
        f"[[money]] Пополнений: <b>{fmt(data['deposits'])}</b>\n"
        f"🛒 Продано: <b>{fmt(data['revenue'])}</b> "
        f"<i>({data['orders']} заказов)</i>\n"
        f"👛 На балансах: <b>{fmt(data['held_balance'])}</b>\n\n"
        "<blockquote>"
        f"[[search]] На проверке: <b>{data['pending_deposits']}</b>\n"
        f"[[support]] Обращений: <b>{data['open_tickets']}</b>\n"
        f"[[warn]] Упавших заказов: <b>{data['failed_orders']}</b>"
        "</blockquote>"
    )


def __getattr__(name: str) -> str:
    """Отдать шаблон с уже подставленными значками."""
    try:
        return substitute(_RAW[name])
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None


def __dir__() -> list[str]:
    return sorted(list(globals()) + list(_RAW))


# Ошибки промокода — словарь, а не шаблон, поэтому собирается отдельно.
PROMO_ERRORS = {
    "not_found": "[[fail]] Такого промокода не существует.",
    "already_used": "[[fail]] Вы уже использовали этот промокод.",
    "exhausted": "[[fail]] Лимит активаций этого промокода исчерпан.",
    "not_for_balance": (
        "[[fail]] Это код на <b>скидку</b>, а не на пополнение.\n\n"
        "<blockquote>Введите его при покупке — на шаге подтверждения "
        "заказа есть кнопка «Промокод».</blockquote>"
    ),
    "not_for_order": (
        "[[fail]] Это код на <b>пополнение баланса</b>, а не на скидку.\n\n"
        "<blockquote>Активируйте его в профиле — там он зачислит деньги "
        "на счёт.</blockquote>"
    ),
}
PROMO_ERRORS = {key: substitute(value) for key, value in PROMO_ERRORS.items()}
