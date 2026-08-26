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
    "<i>Выберите раздел ниже</i> 👇"
)

# ═════════════════════════════════════════════════════════════ звёзды

_RAW["STARS_ENTRY"] = (
    "[[stars]] <b>Telegram Stars</b>\n"
    f"<code>{LINE}</code>\n\n"
    "[[price]] Цена: <b>{rate}</b> за звезду\n\n"
    "<blockquote>Звёзды придут на любой аккаунт с публичным юзернеймом. "
    "Пароль и код из SMS не нужны никогда.</blockquote>\n\n"
    "<i>Нажмите кнопку ниже</i> 👇"
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

# ════════════════════════════════════════════════════════════ premium

_RAW["PREMIUM_ENTRY"] = (
    "[[premium]] <b>Telegram Premium</b>\n"
    f"<code>{LINE}</code>\n\n"
    "<blockquote>Подписка оформляется на аккаунт с публичным юзернеймом. "
    "Доступ к аккаунту не нужен.</blockquote>\n\n"
    "<i>Выберите срок</i> 👇"
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
    "├ К списанию: <b>{price}</b>\n"
    "└ Останется: <b>{rest}</b>\n\n"
    "<blockquote>Нажимая «Оплатить», вы подтверждаете, что аккаунт указан "
    "верно.</blockquote>"
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
    "<i>Выберите способ</i> 👇"
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
    "[[deposit]] <b>Пополнение на {amount}</b>\n"
    f"<code>{LINE}</code>\n\n"
    "{dc_block}"
    "Переведите <b>ровно {amount}</b> по реквизитам:\n\n"
    "<b>Карта</b>\n<code>{card}</code>\n\n"
    "{holder}{bank}"
    "🏙 Город: <b>{city}</b>\n"
    "{extra}\n"
    "<blockquote>[[warn]] Сумма должна совпадать до копейки — иначе "
    "заявку придётся проверять вручную.</blockquote>\n\n"
    "📸 <i>После перевода пришлите скриншот чека сюда.</i>"
)

_RAW["DEPOSIT_DC_BLOCK"] = (
    "<blockquote>[[ok]] <b>Проще всего — кнопкой ниже.</b>\n"
    "Откроется «Душанбе Сити» с уже вписанными счётом и суммой: "
    "останется подтвердить перевод.\n\n"
    "Код платежа: <code>{reference}</code></blockquote>\n\n"
    "<i>Или вручную:</i>\n\n"
)

_RAW["DEPOSIT_NEED_PHOTO"] = (
    "📸 Пришлите <b>фото или файл</b> чека — по тексту оплату не проверить."
)

_RAW["DEPOSIT_SENT"] = (
    "[[ok]] <b>Заявка №{deposit_id} отправлена</b>\n"
    f"<code>{LINE}</code>\n\n"
    "└ Сумма: <b>{amount}</b>\n\n"
    "<blockquote>[[wait]] Проверка занимает несколько минут. Я напишу, "
    "как только баланс пополнится.</blockquote>"
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
    "├ /done &lt;id&gt; · /refund &lt;id&gt; — закрыть или вернуть\n"
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
}
PROMO_ERRORS = {key: substitute(value) for key, value in PROMO_ERRORS.items()}
