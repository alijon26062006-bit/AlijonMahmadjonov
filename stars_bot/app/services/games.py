"""Продажа игровых пополнений: цены, проверка ID, заказ и присмотр за ним.

Три правила, купленные чужим опытом (в документации сервиса они помечены
как «деньги теряли»):

  1. Ответ ok:true означает «заказ принят», а не «алмазы у игрока».
     Почти всегда приходит processing, и настоящий исход узнаётся только
     опросом статуса.
  2. Если не присматривать за такими заказами, они зависают навсегда.
     Поэтому фоновая задача добирает их каждые несколько минут.
  3. У ожидания должен быть конец. Заказ, висящий дольше срока, закрывается
     возвратом денег — иначе клиент остаётся и без денег, и без товара.

Возврат по таймауту — не бесплатное решение: заказ может выполниться
позже, и тогда товар уйдёт даром. Поэтому владельцу шлётся заметное
предупреждение с номером заказа у поставщика, чтобы он проверил кабинет.
"""
from __future__ import annotations

import asyncio
import logging
import re
import uuid
from decimal import ROUND_HALF_UP, Decimal

import aiosqlite
from aiogram import Bot

from app import db, runtime
from app.money import fmt, round_price
from app.services.fragment import DeliveryError, DeliveryUncertain

log = logging.getLogger(__name__)

#: Как часто добирать заказы, оставшиеся в работе.
WATCH_EVERY = 5 * 60
#: Сколько ждём выполнения, прежде чем вернуть деньги.
TIMEOUT_MINUTES = 20

# Сразу после оплаты заказ опрашивается часто: выдача обычно занимает
# секунды, и ждать пятиминутного обхода незачем — клиент всё это время
# сидит с сообщением «пополнение идёт».
#
# Но частота не может быть постоянной. У поставщика лимит в минуту, и
# опрос раз в три секунды — это двадцать запросов в минуту на один
# заказ: три заказа разом съедают весь лимит, и новые покупки встают в
# очередь за проверками чужих.
#
# Поэтому шаг опроса зависит от того, сколько заказов сейчас на руках:
# один опрашиваем часто, сотню — редко, а вместе они укладываются в
# отведённую долю. Выдачу всё равно первым замечает вебхук; опрос —
# страховка на случай, когда он не пришёл.
FAST_EVERY = 3
FAST_SECONDS = 3 * 60
#: Дальше этого не разрежаем: пятиминутный шаг и так даёт общий обход.
FAST_SLOWEST = 5 * 60
#: Какую долю лимита поставщика отдаём под фоновые опросы. Остальное —
#: живым клиентам: заказам, проверкам ID и каталогу.
BACKGROUND_SHARE = 0.4

#: Сколько заказов опрашивается прямо сейчас.
_watching = 0


def poll_every() -> float:
    """Шаг опроса с оглядкой на лимит поставщика и число заказов."""
    from app.services.ratelimit import WINDOW, limit_now

    budget = max(1.0, limit_now() * BACKGROUND_SHARE)
    share = max(1, _watching) * WINDOW / budget
    return min(FAST_SLOWEST, max(FAST_EVERY, share))

#: Метка причины возврата: по ней узнаём заказы, за которыми надо
#: присмотреть и после возврата денег.
TIMEOUT_MARK = "таймаут:"
#: Сколько ещё следим за возвращённым заказом. Поставщик может выполнить
#: его позже — тогда товар ушёл даром, и владелец должен узнать об этом.
AFTER_REFUND_HOURS = 6

DONE = {"completed", "complete", "done", "delivered", "success", "fulfilled"}
# «refund» — так FazerCards помечает заказ, который отменил сам и вернул
# деньги на счёт. Без этого слова бот считал такой заказ «в работе» и
# держал клиента 20 минут до возврата по таймауту.
FAILED = {"failed", "fail", "error", "cancelled", "canceled", "cancel",
          "rejected", "declined", "refund", "refunded", "refunding",
          "returned", "reversed", "expired", "void", "voided"}


def offer_price(usd: Decimal, margin: int) -> int:
    """Цена пакета в дирамах: себестоимость по курсу плюс наценка."""
    rate = runtime.usd_rate()
    if rate <= 0:
        return 0
    cost = usd * rate
    with_margin = cost * (100 + max(margin, 0)) / 100
    return round_price(int(with_margin.to_integral_value(rounding=ROUND_HALF_UP)))


def offer_cost(usd: Decimal) -> int:
    """Во что пакет обходится владельцу, в дирамах."""
    rate = runtime.usd_rate()
    return int((usd * rate).to_integral_value(rounding=ROUND_HALF_UP)) if rate else 0


def margin_of(game: db.Game) -> int:
    return game.margin or runtime.margin_percent()


def idempotency_key(order_id: int) -> str:
    """Уникальный ключ заказа. Один заказ бота — один ключ, поэтому повтор
    запроса не спишет у поставщика деньги дважды."""
    return f"bot-{order_id}-{uuid.uuid5(uuid.NAMESPACE_URL, str(order_id)).hex[:12]}"


#: Из отказа вида Field "player_id" is required достаём имя поля.
FIELD_RE = re.compile(r'[Ff]ield\s+"?([A-Za-z0-9_]+)"?\s+is\s+required')


def missing_field(error: str) -> str | None:
    """Какое поле требует поставщик. None — отказ не про поле."""
    found = FIELD_RE.search(str(error))
    return found.group(1) if found else None


#: Как назвать поле клиенту. Части игр мало одного ID: Magic Chess и
#: Mobile Legends требуют ещё и номер сервера.
FIELD_LABELS: dict[str, str] = {
    "user_id": "ID игрока",
    "player_id": "ID игрока",
    "uid": "ID игрока",
    "account_id": "ID аккаунта",
    "server_id": "ID сервера",
    "zone_id": "ID сервера",
    "zone": "ID сервера",
    "server": "ID сервера",
    "region_id": "ID региона",
    "character_id": "ID персонажа",
    "login": "логин",
    "email": "почта",
}


def field_label(name: str) -> str:
    return FIELD_LABELS.get(name.lower(), name)


#: Каталог поставщика меняется редко, а страниц и поисков по нему много.
#: Держим ненадолго в памяти: иначе каждое нажатие — новый запрос.
_catalog: dict[int, tuple[float, list[dict]]] = {}
CATALOG_TTL = 10 * 60


#: Пакеты каждой категории — отдельный запрос к поставщику. Когда через
#: API отдаётся весь его каталог, таких запросов десятки, и без памяти
#: каждый заход разработчика превращался бы в лавину.
_offers_raw: dict[tuple[int, str], tuple[float, list[dict]]] = {}


def forget_catalog() -> None:
    _catalog.clear()
    _offers_raw.clear()
    _offers_lock.clear()
    # Готовый каталог API собран из этих же данных — он тоже устарел.
    from app.api import catalog as api_catalog

    api_catalog.forget_full()


#: По одному замку на категорию. Нужен не ради порядка, а против
#: лавины: пятьсот клиентов, открывших игру разом, промахиваются мимо
#: памяти все сразу — она ещё пуста, — и уходят к поставщику пятьюстами
#: запросами. Замок пропускает первого, остальные дожидаются его ответа
#: и читают уже готовое.
_offers_lock: dict[tuple[int, str], asyncio.Lock] = {}


async def offers_raw(provider, category_id: str, cached: bool = False) -> list[dict]:
    """Пакеты категории у поставщика.

    cached — отдать запомненное, если оно свежее CATALOG_TTL. Просит об
    этом витрина: пакеты у поставщика меняются раз в дни, а нажатий
    бывают тысячи. Владельцу отдаём живьём — он затем и смотрит, чтобы
    увидеть, что у поставщика прямо сейчас.
    """
    import time

    key = (id(provider), category_id)
    if not cached:
        data = await provider.game_offers(category_id)
        _offers_raw[key] = (time.time(), data)
        return data

    hit = _offers_raw.get(key)
    if hit and time.time() - hit[0] < CATALOG_TTL:
        return hit[1]

    lock = _offers_lock.setdefault(key, asyncio.Lock())
    async with lock:
        # Пока стояли в очереди, ответ мог уже прийти — тогда спрашивать
        # незачем. Ради этой проверки замок и нужен.
        hit = _offers_raw.get(key)
        if hit and time.time() - hit[0] < CATALOG_TTL:
            return hit[1]
        data = await provider.game_offers(category_id)
        _offers_raw[key] = (time.time(), data)
        return data


async def full_catalog(provider, cached: bool = False) -> list[dict]:
    """Все категории поставщика вместе с полями для ID.

    Два списка у сервиса разные: категории — что продаётся, validate-id —
    у чего работает проверка ID. Владельцу нужен первый, а поля берутся
    из второго, поэтому сводим их вместе.
    """
    import time

    key = id(provider)
    if cached:
        hit = _catalog.get(key)
        if hit and time.time() - hit[0] < CATALOG_TTL:
            return hit[1]

    categories: list[dict] = []
    failure: Exception | None = None
    if hasattr(provider, "game_categories"):
        try:
            categories = await provider.game_categories()
        except Exception as exc:  # noqa: BLE001 — попробуем второй список
            log.info("Игры: список категорий не пришёл — %s", exc)
            failure = exc

    try:
        validated = await provider.game_catalog()
    except Exception as exc:  # noqa: BLE001
        log.info("Игры: список validate-id не пришёл — %s", exc)
        validated = []
        # Молчать нельзя: пустой каталог владелец прочтёт как «у
        # поставщика ничего нет», а на деле это оборванная связь или
        # неверный ключ.
        if not categories:
            raise
    if failure is not None and not categories and not validated:
        raise failure

    fields = {item["category_id"]: item.get("fields") or []
              for item in validated}

    merged = {item["category_id"]: dict(item) for item in categories}
    for item in validated:
        merged.setdefault(item["category_id"], dict(item))
    for code, item in merged.items():
        if not item.get("fields") and fields.get(code):
            item["fields"] = fields[code]
        item["checkable"] = code in fields

    out = list(merged.values())
    _catalog[key] = (time.time(), out)
    return out


async def detect_fields(provider, category_id: str) -> list[str]:
    """Какие поля поставщик требует для этой игры. Пусто — не узнали."""
    try:
        catalog = await provider.game_catalog()
    except Exception as exc:  # noqa: BLE001 — не смогли, не беда
        log.info("Игры: каталог полей не пришёл — %s", exc)
        return []

    for item in catalog:
        if item.get("category_id") != category_id:
            continue
        names = []
        for field in item.get("fields") or []:
            name = field.get("name") if isinstance(field, dict) else field
            if name:
                names.append(str(name))
        return names
    return []


async def detect_field(provider, category_id: str) -> str | None:
    """Первое поле ID. Оставлено для мест, где нужно одно имя."""
    names = await detect_fields(provider, category_id)
    return names[0] if names else None


#: Порядок ввода: ID игрока всегда первым, сервер за ним.
FIELD_RANK: dict[str, int] = {
    "user_id": 0, "player_id": 0, "uid": 0, "account_id": 0,
    "server_id": 1, "zone_id": 1, "zone": 1, "server": 1,
    "region_id": 2,
}


def with_field(current: str, wanted: str) -> str:
    """Учесть поле, которого поставщику не хватило.

    Разница принципиальная. «Нужен player_id» вместо нашего user_id —
    это то же самое поле под другим именем, его надо ЗАМЕНИТЬ. А «нужен
    server_id» рядом с player_id — второе поле, его надо ДОБАВИТЬ:
    у Magic Chess и Mobile Legends аккаунт задаётся парой чисел.
    Спутать эти два случая — значит гонять заказы по кругу.
    """
    names = [part.strip() for part in (current or "").split(",") if part.strip()]
    if not wanted or wanted in names:
        return ",".join(names) or wanted

    label = field_label(wanted)
    for index, name in enumerate(names):
        if field_label(name) == label:
            names[index] = wanted        # то же поле, другое имя
            break
    else:
        names.append(wanted)

    names.sort(key=lambda name: FIELD_RANK.get(name.lower(), 9))
    return ",".join(names)


def status_of(order: dict | None) -> str:
    if not isinstance(order, dict):
        return ""
    return str(order.get("status") or order.get("state") or "").strip().lower()


async def place(
    provider, *, game: db.Game, offer_id: str, fields: dict[str, str],
    quantity: int, order_id: int, conn: aiosqlite.Connection | None = None,
) -> str:
    """Отправить заказ поставщику. Возвращает его номер заказа.

    С conn запрос запоминается до отправки: если ответ не дойдёт, по нему
    потом узнаем номер заказа (см. recover).
    """
    if conn is not None:
        await db.save_game_request(
            conn, order_id, category_id=game.category_id, offer_id=offer_id,
            fields=fields, quantity=quantity,
        )
    order = await provider.order_game(
        category_id=game.category_id, offer_id=offer_id,
        fields=fields, quantity=quantity,
        idempotency_key=idempotency_key(order_id),
    )
    external = str(order.get("order_id") or order.get("id") or "")
    status = status_of(order)

    if status in FAILED:
        raise DeliveryError(
            f"Поставщик отклонил заказ: {order.get('error') or status}"
        )
    if not external:
        raise DeliveryUncertain(
            "Поставщик не вернул номер заказа — проверить выдачу нечем."
        )
    return external


async def check(
    bot: Bot, conn: aiosqlite.Connection, provider, order: db.Order,
) -> str:
    """Спросить статус и закрыть заказ, если он решился.

    Возвращает: done | failed | waiting | timeout.
    """
    from app.services import delivery

    if not order.fragment_order_id:
        found = await recover(bot, conn, provider, order)
        if found is None:
            if _minutes_waiting(order) >= timeout_minutes():
                await _refund_nameless(bot, conn, order)
                return "timeout"
            return "waiting"
        order = found

    remote = await provider.order_status(order.fragment_order_id)
    status = status_of(remote)

    if status in DONE:
        if await db.transition_order(
            conn, order.id, expected=order.status, new=db.ORDER_DELIVERED, error=None
        ):
            await delivery.tell_buyer(bot, conn, order, delivery._done_text(order))
            await delivery._ask_review(bot, conn, order)
            log.info("Игры: заказ %s выполнен", order.id)
        return "done"

    if status in FAILED:
        why = _reason_of(remote)
        if await _refund(bot, conn, order, f"поставщик вернул статус {status}"
                         + (f": {why}" if why else "")):
            await delivery.notify_admins(
                bot,
                "⚠️ <b>Поставщик отменил игровой заказ</b>\n"
                f"├ Заказ: <code>{order.id}</code> — {order.title}\n"
                f"├ У поставщика: <code>{order.fragment_order_id}</code> · {status}\n"
                f"├ ID игрока: <code>{order.recipient}</code>\n"
                f"└ Клиенту вернули <b>{fmt(order.price)}</b>\n"
                + (f"\n<blockquote>{why[:300]}</blockquote>\n" if why else "")
                + "\n<blockquote>Если так отменяются все заказы этой игры — "
                "проблема у поставщика: напишите ему с номерами заказов, а "
                "пока уберите игру из меню (панель → 🕹 Игры).</blockquote>",
            )
        return "failed"

    if _minutes_waiting(order) >= timeout_minutes():
        await _refund(bot, conn, order,
                      f"{TIMEOUT_MARK} не выполнился за отведённое время")
        await delivery.notify_admins(
            bot,
            "⚠️ <b>Игровой заказ висел слишком долго</b>\n"
            f"├ Наш номер: <code>{order.id}</code>\n"
            f"├ У поставщика: <code>{order.fragment_order_id}</code>\n"
            f"└ Клиенту вернули <b>{fmt(order.price)}</b>\n\n"
            "<blockquote>Проверьте кабинет поставщика: если заказ всё-таки "
            "прошёл, товар ушёл бесплатно — списать деньги обратно можно "
            "в разделе «Клиенты».</blockquote>",
        )
        return "timeout"

    return "waiting"


#: Метка возврата заказа, так и не получившего номер у поставщика.
NAMELESS_MARK = "без номера:"


async def recover(
    bot: Bot, conn: aiosqlite.Connection, provider, order: db.Order,
) -> db.Order | None:
    """Узнать номер заказа, ответ на который не дошёл.

    Чаще всего поставщик просто ответил дольше 20 секунд: заказ у него
    есть, а номера у нас нет — и следить за ним нечем. Повторяем тот же
    запрос с тем же ключом от дублей: по документации поставщика второй
    раз он деньги не спишет, а вернёт уже созданный заказ. Если первый
    запрос до него не дошёл вовсе — заказ создастся сейчас, клиент ведь
    заплатил.

    Отказ на повторе деньги не возвращает: «тот же ключ ещё выполняется»
    тоже приходит отказом. Возврат — только по общему таймауту.
    """
    request = await db.get_game_request(conn, order.id)
    if request is None:
        return None
    try:
        remote = await provider.order_game(
            category_id=request["category_id"], offer_id=request["offer_id"],
            fields=request["fields"], quantity=request["quantity"],
            idempotency_key=idempotency_key(order.id),
        )
    except (DeliveryError, DeliveryUncertain) as exc:
        log.info("Игры: номер заказа %s пока не узнали — %s", order.id, exc)
        return None
    external = str((remote or {}).get("order_id") or (remote or {}).get("id") or "")
    if not external:
        return None

    await db.update_order(conn, order.id, fragment_order_id=external)
    if order.status == db.ORDER_FAILED:
        await db.transition_order(conn, order.id, expected=db.ORDER_FAILED,
                                  new=db.ORDER_DELIVERING, error=None)
    log.info("Игры: заказ %s нашёлся у поставщика — %s", order.id, external)
    from app.services import delivery

    await delivery.notify_admins(
        bot,
        "✅ <b>Номер заказа нашёлся</b>\n"
        f"├ Наш номер: <code>{order.id}</code>\n"
        f"└ У поставщика: <code>{external}</code>\n\n"
        "Дальше бот следит за ним сам — делать ничего не нужно.",
    )
    return await db.get_order(conn, order.id)


async def _refund_nameless(
    bot: Bot, conn: aiosqlite.Connection, order: db.Order,
) -> None:
    """Номера так и нет, время вышло — вернуть деньги, как обещали."""
    from app.services import delivery

    await _refund(bot, conn, order,
                  f"{NAMELESS_MARK} поставщик так и не дал номер заказа")
    await delivery.notify_admins(
        bot,
        "⚠️ <b>Игровой заказ без номера — деньги вернули</b>\n"
        f"├ Наш номер: <code>{order.id}</code>\n"
        f"├ ID игрока: <code>{order.recipient}</code>\n"
        f"└ Клиенту вернули <b>{fmt(order.price)}</b>\n\n"
        "<blockquote>Поставщик за "
        f"{timeout_minutes()} мин так и не подтвердил заказ. Найдите в его "
        "кабинете заказ на этот ID игрока: если алмазы всё-таки дошли, "
        "спишите деньги обратно — панель → 👥 Клиенты → "
        f"<code>{order.user_id}</code> → ➖ Списать.</blockquote>",
    )


def timeout_minutes() -> int:
    """Сколько ждать выдачу. Меняется в панели: у разных игр своя скорость."""
    return max(runtime.get_int("games_timeout_min") or TIMEOUT_MINUTES, 2)


async def check_after_refund(bot: Bot, conn: aiosqlite.Connection, provider) -> int:
    """Догнать заказы, которые выполнились уже после возврата денег.

    Возврат по таймауту — ставка: заказ мог дойти позже, и тогда товар ушёл
    бесплатно. Молча это оставлять нельзя.
    """
    from datetime import datetime, timedelta, timezone

    since = (datetime.now(timezone.utc)
             - timedelta(hours=AFTER_REFUND_HOURS)).isoformat(timespec="seconds")
    found = 0
    for order in await db.refunded_game_orders(conn, TIMEOUT_MARK, since):
        remote = await provider.order_status(order.fragment_order_id or "")
        if status_of(remote) not in DONE:
            continue

        # Метку снимаем сразу: иначе о том же заказе напишем на каждом круге.
        await db.update_order(
            conn, order.id,
            error=f"выполнен после возврата ({order.fragment_order_id})",
        )
        found += 1
        from app.services import delivery

        await delivery.notify_admins(
            bot,
            "❗️ <b>Заказ выполнился после возврата</b>\n"
            f"├ Наш номер: <code>{order.id}</code>\n"
            f"├ У поставщика: <code>{order.fragment_order_id}</code>\n"
            f"├ Игрок: <code>{order.recipient}</code>\n"
            f"└ Клиенту вернули <b>{fmt(order.price)}</b>\n\n"
            "<blockquote>Товар дошёл, а деньги вернулись — клиент получил "
            "его бесплатно. Списать обратно: панель → 👥 Клиенты → "
            f"<code>{order.user_id}</code> → ➖ Списать.\n\n"
            "Если это повторяется, увеличьте время ожидания в разделе "
            "«Игры».</blockquote>",
        )
    return found


def _minutes_waiting(order: db.Order) -> int:
    from datetime import datetime, timezone

    try:
        created = datetime.fromisoformat(order.created_at)
    except ValueError:
        return 0
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return int((datetime.now(timezone.utc) - created).total_seconds() // 60)


def _reason_of(remote) -> str:
    """Причину отмены поставщик кладёт в разные поля — берём первую."""
    if not isinstance(remote, dict):
        return ""
    for key in ("error", "reason", "message", "comment", "note"):
        value = remote.get(key)
        if isinstance(value, dict):
            value = value.get("message") or value.get("code")
        if value:
            return str(value).strip()
    return ""


async def _refund(
    bot: Bot, conn: aiosqlite.Connection, order: db.Order, reason: str,
) -> bool:
    """Вернуть деньги. False — заказ уже закрыл кто-то другой."""
    from app import texts
    from app.services import delivery

    if not await db.transition_order(
        conn, order.id, expected=order.status, new=db.ORDER_REFUNDED,
        error=reason[:1000],
    ):
        return False
    await delivery._give_back(conn, await db.get_order(conn, order.id) or order)
    await delivery.tell_buyer(
        bot, conn, order,
        texts.REFUNDED.format(
            order_id=order.id, price=fmt(order.price), support=texts.support()
        ),
    )
    log.warning("Игры: заказ %s возвращён — %s", order.id, reason)
    return True


async def follow(bot: Bot, provider, order_id: int) -> str:
    """Досмотреть свежий заказ до конца, опрашивая часто.

    Своё соединение с базой: задача живёт дольше обработчика, и его
    соединение к этому моменту уже закрыто.
    """
    global _watching

    waited = 0
    _watching += 1
    conn = await db.connect()
    try:
        while waited < FAST_SECONDS:
            step = poll_every()
            await asyncio.sleep(step)
            waited += step

            order = await db.get_order(conn, order_id)
            if order is None or order.status not in (db.ORDER_DELIVERING,
                                                     db.ORDER_FAILED):
                return "done"
            try:
                result = await check(bot, conn, provider, order)
            except Exception as exc:  # noqa: BLE001 — подхватит общий обход
                log.info("Игры: быстрый опрос заказа %s сорвался — %s",
                         order_id, exc)
                return "waiting"
            if result != "waiting":
                log.info("Игры: заказ %s закрылся за ~%s сек (%s)",
                         order_id, waited, result)
                return result
    finally:
        _watching -= 1
        await conn.close()
    return "waiting"


async def watch_loop(provider, bot: Bot) -> None:
    """Фоновый присмотр: заказ без присмотра зависает навсегда."""
    while True:
        try:
            await asyncio.sleep(WATCH_EVERY)
            from app.services import suppliers

            conn = await db.connect()
            try:
                games_provider = suppliers.for_games(provider)
                pending = await db.unfinished_game_orders(conn)
                for order in pending:
                    await check(bot, conn, games_provider, order)
                await check_after_refund(bot, conn, games_provider)
            finally:
                await conn.close()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — фон не должен умирать
            log.exception("Игры: присмотр за заказами упал: %s", exc)
            await asyncio.sleep(60)


async def refund_place(
    bot: Bot, conn: aiosqlite.Connection, order: db.Order, game: db.Game, exc,
) -> str:
    """Поставщик отказал: вернуть деньги, поправить поле, позвать владельца.

    Возвращает приписку о починке поля — обработчик показывает её
    владельцу вместе с остальным. Общая на бота и на API нарочно: два
    разных разбора одной ошибки разошлись бы при первой же правке.
    """
    from app.services import delivery

    await _refund(bot, conn, order, str(exc))

    # Поставщик сам называет поле, которого ему не хватило. Добавляем
    # его к набору — именно добавляем: жалуется он по одному полю за
    # раз, и замена гоняла бы заказы по кругу.
    fixed = ""
    wanted = missing_field(str(exc))
    if wanted and wanted not in game.field_names:
        updated = with_field(game.field, wanted)
        await db.update_game(conn, game.category_id, field=updated)
        asked = ", ".join(field_label(n) for n in updated.split(","))
        fixed = (f"\n\n✅ <b>Поля исправлены:</b> <code>{updated}</code>\n"
                 f"Теперь бот спрашивает: <b>{asked}</b>.\n"
                 "Следующий заказ пройдёт — попросите клиента повторить.")

    await delivery.notify_admins(
        bot,
        "⚠️ <b>Игровой заказ не прошёл</b>\n"
        f"├ Заказ: <code>{order.id}</code> — {game.title}\n"
        f"└ Клиенту вернули <b>{fmt(order.price)}</b>\n\n"
        f"<blockquote expandable>{str(exc)[:600]}</blockquote>{fixed}",
    )
    return fixed


async def hold_place(
    bot: Bot, conn: aiosqlite.Connection, order: db.Order, game: db.Game,
    exc, player: str,
) -> None:
    """Номера у поставщика нет: деньги придержать, позвать владельца.

    Автовозврата здесь быть не может — неизвестно, ушёл товар или нет,
    и вернуть деньги значило бы раздать его бесплатно.
    """
    from app.services import delivery

    await db.transition_order(
        conn, order.id, expected=db.ORDER_DELIVERING, new=db.ORDER_FAILED,
        error=str(exc)[:1000],
    )
    await delivery.notify_admins(
        bot,
        "⚠️ <b>Игровой заказ без номера у поставщика</b>\n"
        f"├ Заказ: <code>{order.id}</code> — {game.title}\n"
        f"├ ID игрока: <code>{player}</code>\n"
        f"└ Списано: <b>{fmt(order.price)}</b>\n\n"
        f"<blockquote expandable>{str(exc)[:600]}</blockquote>\n\n"
        "<blockquote>Скорее всего, поставщик ответил слишком долго. Бот "
        "сам переспросит его раз в 5 минут и, если заказ там есть, дальше "
        "будет следить за ним сам.\n\nМожно решить и руками — кабинет "
        f"поставщика: дошло → <code>/done {order.id}</code>, "
        f"нет → <code>/refund {order.id}</code>.\n\nБез решения деньги "
        f"вернутся клиенту сами через {timeout_minutes()} мин."
        "</blockquote>",
    )


async def order_now(
    bot: Bot, conn: aiosqlite.Connection, provider, *, game: db.Game,
    offer_id: str, fields: dict[str, str], order: db.Order,
) -> db.Order:
    """Отправить уже оплаченный игровой заказ поставщику.

    Деньги списаны и заказ заведён снаружи — так API успевает связать его
    со своим ключом до первой выдачи. Здесь только отправка и разбор
    отказа, общий с ботом.
    """
    try:
        external = await place(
            provider, game=game, offer_id=offer_id, fields=fields,
            quantity=1, order_id=order.id, conn=conn,
        )
    except DeliveryError as exc:
        await refund_place(bot, conn, order, game, exc)
        return await db.get_order(conn, order.id) or order
    except DeliveryUncertain as exc:
        await hold_place(bot, conn, order, game, exc, order.recipient)
        return await db.get_order(conn, order.id) or order

    await db.update_order(conn, order.id, fragment_order_id=external)

    # Заказ почти всегда уходит в processing, поэтому проверяем сразу —
    # вдруг он уже готов, — а дальше за ним следит фоновая задача.
    fresh = await db.get_order(conn, order.id)
    if fresh and await check(bot, conn, provider, fresh) == "waiting":
        asyncio.create_task(follow(bot, provider, order.id))
    return await db.get_order(conn, order.id) or order
