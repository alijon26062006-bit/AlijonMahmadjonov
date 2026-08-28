"""Выдача через FazerCards (api.fzr.cards).

Для владельца это самая простая схема из всех: пополняешь баланс реселлера
один раз, дальше бот списывает с него сам. Сид-фраза кошелька не нужна,
авторизация — обычный ключ X-API-Key.

ВАЖНО про асинхронность: в документации сказано «balance debited
immediately; fulfillment is asynchronous». То есть успешный ответ на
покупку означает лишь, что деньги списаны и заказ принят, а не что звёзды
у получателя. Поэтому после покупки бот дожидается статуса заказа и только
тогда пишет клиенту «выполнено».

Цены сервис отдаёт в долларах, поэтому себестоимость в сомони считается
через курс доллара, заданный в панели.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import aiohttp

from app.config import settings
from app.services.fragment import (
    DeliveryError, DeliveryProvider, DeliveryResult, DeliveryUncertain, Recipient,
    SteamAccount,
)

log = logging.getLogger(__name__)

STARS_QUOTE = "/api/v2/telegram/stars"
PREMIUM_QUOTE = "/api/v2/telegram/premium"
STARS_BUY = "/api/v2/telegram/stars/buy"
PREMIUM_BUY = "/api/v2/telegram/premium/buy"

# Пополнение кошелька Steam
STEAM_RATES = "/api/v2/steam-topup/rates"
STEAM_CHECK = "/api/v2/steam-topup/check-login"
STEAM_ORDER = "/api/v2/steam-topup/order"

#: Где в ответе может лежать курс/цена единицы пополнения Steam.
STEAM_RATE_KEYS = ["rate", "price", "price_usd", "usd", "usd_rate",
                   "price_per_unit", "value"]
#: Где — валюта кошелька.
STEAM_CURRENCY_KEYS = ["currency", "wallet_currency", "code", "name"]
#: Где — признак «такой логин существует».
STEAM_OK_KEYS = ["exists", "valid", "found", "ok", "success", "is_valid"]
#: Где — отображаемое имя аккаунта.
STEAM_NAME_KEYS = ["name", "nickname", "persona", "persona_name", "display_name",
                   "account_name", "steam_name"]

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=45)

# Формулировки статусов могут отличаться, поэтому распознаём широкий набор,
# а незнакомое считаем «ещё в работе»: соврать клиенту дороже, чем подождать.
DONE = {"completed", "complete", "done", "delivered", "success", "successful",
        "fulfilled", "finished", "paid", "ok"}
FAILED = {"failed", "fail", "error", "cancelled", "canceled", "rejected",
          "declined", "refunded", "expired"}
PENDING = {"pending", "processing", "in_progress", "inprogress", "queued",
           "new", "created", "accepted", "waiting", "running", "fulfilling"}


# Вероятные пути к балансу и заказам. Документация в руках владельца, но
# перебрать варианты ключом быстрее, чем сверять скриншоты вручную.
BALANCE_CANDIDATES = [
    "/api/v2/account", "/api/v2/account/balance", "/api/v2/account/me",
    "/api/v2/account/info", "/api/v2/balance", "/api/v2/me",
    "/api/v2/user", "/api/v2/user/balance", "/api/v2/profile",
    "/api/v2/reseller", "/api/v2/reseller/balance", "/api/v2/wallet",
    "/api/v2/payment/balance", "/api/v2/subscription",
]
ORDER_LIST_CANDIDATES = [
    "/api/v2/orders", "/api/v2/order", "/api/v2/orders/list",
    "/api/v2/account/orders", "/api/v2/my/orders",
]
# Шаблоны одиночного заказа. Пробуются по очереди, рабочий запоминается.
ORDER_ONE_CANDIDATES = [
    "/api/v2/orders/{order_id}", "/api/v2/order/{order_id}",
    "/api/v2/orders/{order_id}/status", "/api/v2/account/orders/{order_id}",
]


@dataclass
class CostEstimate:
    """Во что заказ обходится владельцу. Цены FazerCards уже в долларах."""
    quantity: int
    amount: str
    currency: str
    usd_total: Decimal
    usd_per_unit: Decimal
    usdt_per_ton: str = ""


def _first(holder, keys: list[str]):
    """Первое непустое значение из набора ключей."""
    if not isinstance(holder, dict):
        return None
    for key in keys:
        value = holder.get(key)
        if value not in (None, ""):
            return value
    return None


def _decimal(value, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise DeliveryError(f"FazerCards вернул нечисловое поле {field}: {value!r}") from exc


class FazerProvider(DeliveryProvider):
    supports_name_lookup = False   # проверки юзернейма у сервиса нет
    instant = True                 # деньги списываются с баланса сразу

    def __init__(self) -> None:
        if not settings.fazer_api_key:
            raise RuntimeError("Не задан FAZER_API_KEY")
        self._base = settings.fazer_base_url.rstrip("/")
        self._session: aiohttp.ClientSession | None = None

    # ------------------------------------------------------------ транспорт

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=REQUEST_TIMEOUT,
                headers={
                    "X-API-Key": settings.fazer_api_key,
                    "Accept": "application/json",
                },
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    @staticmethod
    def _explain(data: dict, status: int) -> str:
        for key in ("error", "message", "blockReason", "detail"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                code = data.get("code")
                return f"{value.strip()}" + (f" [{code}]" if code else "")
        return str(data)[:250] or f"HTTP {status}"

    async def _request(
        self, method: str, path: str, payload: dict | None = None, *, safe: bool = False
    ) -> dict:
        """safe=True — запрос ничего не меняет, поэтому сетевой сбой можно
        считать обычной ошибкой, а не неопределённым исходом."""
        session = await self._get_session()
        try:
            async with session.request(method, self._base + path, json=payload) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:  # noqa: BLE001 — при сбое может прийти HTML
                    data = {"raw": (await resp.text())[:250]}
                if not isinstance(data, dict):
                    data = {"response": data}

                if resp.status in (502, 503) or resp.status >= 500:
                    message = self._explain(data, resp.status)
                    raise (DeliveryError if safe else DeliveryUncertain)(
                        f"FazerCards недоступен ({resp.status}): {message}"
                    )
                if resp.status >= 400:
                    raise DeliveryError(self._explain(data, resp.status))

                # Сервис оборачивает данные в {ok: ...}; ok=false — отказ.
                if data.get("ok") is False:
                    raise DeliveryError(self._explain(data, resp.status))
                return data

        except (TimeoutError, aiohttp.ClientError) as exc:
            raise (DeliveryError if safe else DeliveryUncertain)(
                f"Нет связи с FazerCards: {exc}"
            ) from exc

    # --------------------------------------------------------------- цены

    async def stars_quote(self) -> dict:
        return await self._request("GET", STARS_QUOTE, safe=True)

    async def premium_quote(self) -> dict:
        return await self._request("GET", PREMIUM_QUOTE, safe=True)

    async def cost_estimate(self, product_type: str, amount: int) -> CostEstimate:
        """Себестоимость заказа в долларах — цены сервис отдаёт сразу в USD."""
        if amount <= 0:
            raise DeliveryError("Количество должно быть больше нуля.")

        if product_type == "stars":
            data = await self.stars_quote()
            per_unit = _decimal(data.get("price_per_star"), "price_per_star")
            total = per_unit * amount
        else:
            data = await self.premium_quote()
            plans = {int(p["months"]): p["price_usd"] for p in data.get("plans", [])}
            if amount not in plans:
                raise DeliveryError(
                    f"FazerCards не продаёт Premium на {amount} мес. "
                    f"Доступно: {', '.join(map(str, sorted(plans))) or '—'}"
                )
            total = _decimal(plans[amount], "price_usd")
            per_unit = total / amount

        return CostEstimate(
            quantity=amount, amount=f"{total:.4f}", currency="usd",
            usd_total=total, usd_per_unit=per_unit,
        )

    # --------------------------------------------------------------- Steam

    async def steam_rates(self) -> dict:
        return await self._request("GET", STEAM_RATES, safe=True)

    async def steam_rate(self) -> tuple[Decimal, str]:
        """Во что обходится единица пополнения Steam и в какой она валюте.

        Имена полей в документации не сверялись, поэтому берём первое
        подходящее из набора — как это уже сделано с адресами заказов.
        """
        data = await self.steam_rates()
        holder = data
        for key in ("rate", "rates", "data", "result"):
            value = data.get(key)
            if isinstance(value, dict):
                holder = value
                break
            if isinstance(value, list) and value and isinstance(value[0], dict):
                holder = value[0]
                break

        raw = _first(holder, STEAM_RATE_KEYS)
        if raw is None:
            raise DeliveryError(
                f"FazerCards не вернул курс Steam: {str(data)[:200]}"
            )
        currency = str(_first(holder, STEAM_CURRENCY_KEYS) or "RUB").upper()
        return _decimal(raw, "steam rate"), currency

    async def check_steam_login(self, login: str) -> SteamAccount | None:
        """Проверить логин до оплаты. None — сервис ответить не смог."""
        try:
            data = await self._request(
                "POST", STEAM_CHECK, {"login": login}, safe=True,
            )
        except DeliveryError as exc:
            log.info("Steam: логин %s не проверился — %s", login, exc)
            return None

        holder = data.get("account") if isinstance(data.get("account"), dict) else data
        flag = _first(holder, STEAM_OK_KEYS)
        if flag is None:
            # Ответ есть, но признака нет — не выдаём его за проверку.
            return None
        return SteamAccount(
            login=login,
            exists=bool(flag) and str(flag).lower() not in ("0", "false", "no"),
            name=str(_first(holder, STEAM_NAME_KEYS) or ""),
            raw=data,
        )

    async def deliver_steam(self, login: str, amount: int) -> DeliveryResult:
        return await self._buy(STEAM_ORDER, {"login": login, "amount": amount})

    async def limits(self) -> tuple[int, int]:
        """Разрешённый диапазон количества звёзд у сервиса."""
        data = await self.stars_quote()
        return int(data.get("min_amount") or 50), int(data.get("max_amount") or 10_000)

    # ------------------------------------------------------------- выдача

    async def deliver_stars(self, username: str, amount: int) -> DeliveryResult:
        return await self._buy(STARS_BUY, {
            "telegram_username": username, "quantity": amount,
        })

    async def deliver_premium(self, username: str, months: int) -> DeliveryResult:
        return await self._buy(PREMIUM_BUY, {
            "telegram_username": username, "months": months,
        })

    async def _buy(self, path: str, payload: dict) -> DeliveryResult:
        data = await self._request("POST", path, payload)
        order = data.get("order")
        if not isinstance(order, dict):
            raise DeliveryUncertain(
                f"FazerCards принял заказ, но не вернул его данные: {str(data)[:200]}"
            )

        order_id = _order_id(order)
        status = _status(order)
        log.info("FazerCards: заказ %s принят, статус %s", order_id, status or "—")

        # Деньги уже списаны с баланса реселлера. Если статус сразу
        # финальный — незачем опрашивать.
        if status in DONE:
            return DeliveryResult(order_id=order_id, raw=order)
        if status in FAILED:
            raise DeliveryError(f"Заказ {order_id} отклонён: {_reason(order)}")

        if order_id is None:
            raise DeliveryUncertain(
                "FazerCards не вернул номер заказа — проверить выдачу нечем."
            )
        return DeliveryResult(order_id=order_id, raw=await self._await_order(order_id))

    async def _await_order(self, order_id: str) -> dict:
        """Дождаться финального статуса заказа.

        Путь к статусу задаётся в настройках: раздел Orders в документации
        сервиса ещё не сверялся, и угадывать молча нельзя.
        """
        interval = max(settings.task_poll_interval, 2)
        deadline = settings.task_poll_timeout
        waited = 0
        last: dict = {}
        unknown: set[str] = set()

        while waited < deadline:
            await asyncio.sleep(interval)
            waited += interval
            order = await self._read_order(order_id)
            if order is None:
                log.warning("Заказ %s: статус не прочитался", order_id)
                continue
            last = order
            status = _status(order)

            if status in DONE:
                log.info("Заказ %s выполнен за ~%s сек", order_id, waited)
                return order
            if status in FAILED:
                raise DeliveryError(f"Заказ {order_id}: {_reason(order)}")
            if status and status not in PENDING and status not in unknown:
                unknown.add(status)
                log.warning("Заказ %s: незнакомый статус %r — жду дальше",
                            order_id, status)

        raise DeliveryUncertain(
            f"Заказ {order_id} не завершился за {deadline} сек "
            f"(последний статус: {_status(last) or '—'})"
        )

    async def _read_order(self, order_id: str) -> dict | None:
        """Прочитать заказ: сперва известным адресом, потом перебором,
        а если одиночного адреса нет — поиском в списке заказов."""
        known = self.order_path()
        templates = ([known] if known else []) + [
            t for t in ORDER_ONE_CANDIDATES if t != known
        ]

        for template in templates:
            status, data = await self._get_raw(template.format(order_id=order_id))
            if not self._looks_ok(status, data):
                continue
            order = data.get("order") if isinstance(data.get("order"), dict) else data
            if _order_id(order) or _status(order):
                if template != known:
                    await self._remember("fazer_order_path", template)
                    log.info("FazerCards: адрес заказа найден — %s", template)
                return order

        # Одиночного адреса нет — ищем свой заказ в общем списке.
        for path in ORDER_LIST_CANDIDATES:
            status, data = await self._get_raw(path)
            if not self._looks_ok(status, data):
                continue
            found = _find_in_list(data, order_id)
            if found is not None:
                log.info("Заказ %s найден в списке %s", order_id, path)
                return found
        return None

    # ------------------------------------------------------------- прочее

    async def resolve_recipient(self, username: str) -> Recipient | None:
        """Проверки юзернейма у сервиса нет — возвращаем непроверенного,
        и бот честно скажет об этом покупателю."""
        return Recipient(username=username, name="", verified=False)

    @staticmethod
    def balance_path() -> str:
        from app import runtime

        return runtime.get("fazer_balance_path") or settings.fazer_balance_path

    @staticmethod
    def order_path() -> str:
        from app import runtime

        return runtime.get("fazer_order_path") or settings.fazer_order_path

    async def _get_raw(self, path: str) -> tuple[int, dict]:
        """GET без исключений: нужен для перебора адресов."""
        session = await self._get_session()
        try:
            async with session.get(self._base + path) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:  # noqa: BLE001
                    data = {}
                if not isinstance(data, dict):
                    data = {"data": data}
                return resp.status, data
        except (TimeoutError, aiohttp.ClientError) as exc:
            return 0, {"error": str(exc)}

    @staticmethod
    def _looks_ok(status: int, data: dict) -> bool:
        return status == 200 and data.get("ok") is not False

    async def _remember(self, key: str, value: str) -> None:
        """Запомнить найденный адрес, чтобы больше не перебирать."""
        from app import runtime

        try:
            from app import db

            conn = await db.connect()
            try:
                await runtime.set_value(conn, key, value)
            finally:
                await conn.close()
        except Exception as exc:  # noqa: BLE001 — не смогли сохранить, не беда
            log.warning("Адрес %s не сохранился: %s", key, exc)
            runtime._cache[key] = value

    async def find_balance(self) -> tuple[str, dict] | None:
        """Найти рабочий адрес баланса, начиная с уже известного."""
        known = self.balance_path()
        for path in ([known] if known else []) + [
            p for p in BALANCE_CANDIDATES if p != known
        ]:
            status, data = await self._get_raw(path)
            if self._looks_ok(status, data) and _balance_of(data) is not None:
                if path != known:
                    await self._remember("fazer_balance_path", path)
                    log.info("FazerCards: адрес баланса найден — %s", path)
                return path, data
        return None

    async def probe_paths(self) -> dict:
        """Перебрать вероятные адреса и вернуть те, что отвечают.

        Запросы только читающие, ничего не меняют и денег не тратят.
        """
        found: dict[str, list[tuple[str, str]]] = {"balance": [], "orders": []}
        session = await self._get_session()

        async def try_path(path: str) -> tuple[int, dict]:
            try:
                async with session.get(self._base + path) as resp:
                    try:
                        data = await resp.json(content_type=None)
                    except Exception:  # noqa: BLE001
                        data = {}
                    return resp.status, data if isinstance(data, dict) else {"data": data}
            except (TimeoutError, aiohttp.ClientError) as exc:
                return 0, {"error": str(exc)}

        for path in BALANCE_CANDIDATES:
            status, data = await try_path(path)
            if status == 200 and data.get("ok") is not False:
                found["balance"].append((path, _preview(data)))
            await asyncio.sleep(0.2)   # не долбим сервис пачкой запросов

        for path in ORDER_LIST_CANDIDATES:
            status, data = await try_path(path)
            if status == 200 and data.get("ok") is not False:
                found["orders"].append((path, _preview(data)))
            await asyncio.sleep(0.2)

        return found

    async def get_balance(self) -> str:
        found = await self.find_balance()
        if found is None:
            raise DeliveryError(
                "Не нашёл адрес баланса. Нажмите «🔍 Найти адреса API» "
                "или пришлите раздел Account документации."
            )
        _, data = found
        value = _balance_of(data)
        currency = data.get("currency") or (data.get("account") or {}).get("currency") or "USD"
        return f"{value} {currency}"

    async def healthcheck(self) -> dict:
        steps: list[tuple[str, str]] = []
        try:
            stars = await self.stars_quote()
        except (DeliveryError, DeliveryUncertain) as exc:
            steps.append(("Ключ FazerCards", f"❌ {exc}"))
            return {"ok": False, "mode": "fazer", "steps": steps, "error": str(exc)}

        steps.append(("Ключ FazerCards", "✅ принят"))
        steps.append(("Цена звезды", f"✅ ${stars.get('price_per_star')} "
                                     f"({stars.get('min_amount')}–{stars.get('max_amount')} шт.)"))

        try:
            plans = (await self.premium_quote()).get("plans", [])
            steps.append(("Premium", "✅ " + ", ".join(
                f"{p['months']} мес — ${p['price_usd']}" for p in plans) or "—"))
        except (DeliveryError, DeliveryUncertain) as exc:
            steps.append(("Premium", f"⚠️ {exc}"))

        found = await self.find_balance()
        if found is None:
            steps.append(("Баланс реселлера", "⚠️ адрес не найден — нажмите «Найти адреса API»"))
        else:
            path, data = found
            steps.append((
                "Баланс реселлера",
                f"✅ {_balance_of(data)} {data.get('currency', 'USD')}  ({path})",
            ))

        # Проверяем не «записан ли путь», а можем ли мы вообще читать заказы:
        # без этого бот не подтвердит выдачу и будет дёргать владельца.
        reachable = await self._orders_reachable()
        if reachable:
            steps.append(("Чтение заказов", f"✅ {reachable}"))
            ok = True
        else:
            steps.append((
                "Чтение заказов",
                "❌ ни один адрес не отвечает — бот не сможет подтвердить "
                "выдачу и отдаст каждый заказ вам на проверку",
            ))
            ok = False
        return {
            "ok": ok, "mode": "fazer", "steps": steps,
            "error": "" if ok else "Не удалось найти адрес заказов",
        }

    async def _orders_reachable(self) -> str:
        """Есть ли вообще способ прочитать заказы. Возвращает рабочий адрес."""
        for path in ORDER_LIST_CANDIDATES:
            status, data = await self._get_raw(path)
            if self._looks_ok(status, data):
                return path
        # Списка нет — возможно, доступен только одиночный заказ. Проверить
        # его без настоящего номера нельзя, поэтому честно говорим «не знаем».
        return ""


def _order_id(order: dict) -> str | None:
    for key in ("id", "order_id", "uuid", "number", "orderId"):
        value = order.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _status(order: dict) -> str:
    if not isinstance(order, dict):
        return ""
    for key in ("status", "state", "order_status"):
        value = order.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return ""


def _reason(order: dict) -> str:
    for key in ("error", "reason", "failure_reason", "message", "comment"):
        value = order.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return _status(order) or "причина не указана"


def _preview(data: dict) -> str:
    """Короткая выжимка ответа — чтобы владелец узнал нужный путь по виду."""
    interesting = {}
    for key in ("balance", "amount", "available", "funds", "currency",
                "orders", "items", "data", "total", "count"):
        if key in data:
            interesting[key] = data[key]
    if not interesting and isinstance(data.get("account"), dict):
        interesting = data["account"]
    text = str(interesting or data)
    return text[:160]


def _balance_of(data: dict):
    """Достать сумму баланса из ответа любой формы."""
    for source in (data, data.get("account"), data.get("data"), data.get("user")):
        if not isinstance(source, dict):
            continue
        for key in ("balance", "amount", "available", "funds", "credit"):
            value = source.get(key)
            if isinstance(value, (int, float, str)) and str(value).strip():
                return value
            if isinstance(value, dict):
                for inner in ("amount", "value", "total"):
                    if value.get(inner) is not None:
                        return value[inner]
    return None


def _find_in_list(data: dict, order_id: str) -> dict | None:
    """Найти заказ по номеру в списке заказов."""
    for key in ("orders", "items", "data", "results", "list"):
        rows = data.get(key)
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict) and str(_order_id(row) or "") == str(order_id):
                    return row
    return None
