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
)

log = logging.getLogger(__name__)

STARS_QUOTE = "/api/v2/telegram/stars"
PREMIUM_QUOTE = "/api/v2/telegram/premium"
STARS_BUY = "/api/v2/telegram/stars/buy"
PREMIUM_BUY = "/api/v2/telegram/premium/buy"

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
    "/api/v2/account", "/api/v2/account/balance", "/api/v2/balance",
    "/api/v2/me", "/api/v2/user", "/api/v2/profile", "/api/v2/account/me",
    "/api/v2/reseller", "/api/v2/reseller/balance", "/api/v2/account/info",
    "/api/v2/wallet", "/api/v2/subscription",
]
ORDER_LIST_CANDIDATES = [
    "/api/v2/orders", "/api/v2/order", "/api/v2/orders/list",
    "/api/v2/account/orders",
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
        path_template = self.order_path()
        if not path_template:
            raise DeliveryUncertain(
                f"Заказ {order_id} принят, но проверять его статус нечем: "
                "не задан FAZER_ORDER_PATH."
            )

        interval = max(settings.task_poll_interval, 2)
        deadline = settings.task_poll_timeout
        waited = 0
        last: dict = {}
        unknown: set[str] = set()

        while waited < deadline:
            await asyncio.sleep(interval)
            waited += interval
            try:
                last = await self._request(
                    "GET", path_template.format(order_id=order_id), safe=True
                )
            except DeliveryError as exc:
                log.warning("Заказ %s: статус не прочитался (%s)", order_id, exc)
                continue

            order = last.get("order") if isinstance(last.get("order"), dict) else last
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
        path = self.balance_path()
        if not path:
            return "путь к балансу не задан (FAZER_BALANCE_PATH)"
        data = await self._request("GET", path, safe=True)
        for key in ("balance", "amount", "available", "funds"):
            value = data.get(key) or (data.get("account") or {}).get(key)
            if value is not None:
                return f"{value} {data.get('currency', 'USD')}"
        return str(data)[:200]

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

        try:
            steps.append(("Баланс реселлера", "✅ " + await self.get_balance()))
        except Exception as exc:  # noqa: BLE001
            steps.append(("Баланс реселлера", f"⚠️ не прочитался: {exc}"))

        order_path = self.order_path()
        if not order_path:
            steps.append((
                "Проверка заказов",
                "❌ не настроена — бот не подтвердит выдачу и отдаст каждый "
                "заказ вам на разбор.",
            ))
            return {
                "ok": False, "mode": "fazer", "steps": steps,
                "error": "Не задан путь проверки статуса заказа",
            }
        # Галочку тут ставить нельзя: путь можно проверить только на реальном
        # заказе, а до первой покупки он остаётся предположением.
        steps.append((
            "Проверка заказов",
            f"⏳ {order_path} — задан, но ещё не проверен на живом заказе",
        ))
        return {"ok": True, "mode": "fazer", "steps": steps, "error": ""}


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
