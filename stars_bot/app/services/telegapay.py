"""Приём платежей через TelegaPAY (secure.telegapay.link).

Второй способ пополнения рядом с Душанбе Сити: рубли, USDT, TON. Сомони
шлюз не поддерживает, поэтому сумма пересчитывается по курсу из панели.

Схема работы без вебхука: бот создаёт платёжную ссылку, отдаёт её клиенту
и сам спрашивает статус, пока платёж не закроется. Так не нужен ни домен,
ни сертификат, ни открытый порт на сервере.

Осторожность в статусах намеренная: баланс пополняется только на явно
успешном статусе из белого списка. Незнакомый статус считается
неоплаченным — начислить деньги за непрошедший платёж хуже, чем подождать.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import aiohttp

log = logging.getLogger(__name__)

BASE_URL = "https://secure.telegapay.link/api/v1"
TIMEOUT = aiohttp.ClientTimeout(total=30)

# Как шлюз ждёт ключ. Проверяется один раз, рабочий вариант запоминается.
AUTH_HEADERS = [
    ("API-KEY", "{key}"),
    ("X-API-Key", "{key}"),
    ("Authorization", "Bearer {key}"),
    ("Authorization", "{key}"),
    ("api-key", "{key}"),
]

PAID = {"paid", "success", "successful", "completed", "complete", "done",
        "confirmed", "approved", "finished"}
FAILED = {"failed", "fail", "error", "cancelled", "canceled", "rejected",
          "declined", "expired", "timeout", "refunded"}

#: Где в ответе может лежать ссылка на оплату.
LINK_KEYS = ["payment_url", "pay_url", "paylink", "url", "link", "redirect_url"]
#: Где может лежать идентификатор транзакции.
ID_KEYS = ["transaction_id", "payment_id", "id", "uuid", "order_id", "tx_id"]
#: Где может лежать статус.
STATUS_KEYS = ["status", "state", "payment_status", "transaction_status"]
#: Где может лежать реально оплаченная сумма (при подмене суммы).
AMOUNT_KEYS = ["real_amount", "amount_real", "paid_amount", "amount"]


class PaymentError(RuntimeError):
    """Шлюз ответил отказом — платёж создать не удалось."""


@dataclass
class Paylink:
    url: str
    transaction_id: str
    amount: Decimal
    raw: dict


@dataclass
class Status:
    raw_status: str
    paid: bool
    failed: bool
    amount: Decimal | None
    raw: dict


def dig(data, keys: list[str]):
    """Найти первое подходящее значение — хоть в корне, хоть в data/result."""
    for holder in (data, (data or {}).get("data"), (data or {}).get("result"),
                   (data or {}).get("payment"), (data or {}).get("transaction")):
        if isinstance(holder, dict):
            for key in keys:
                value = holder.get(key)
                if value not in (None, ""):
                    return value
    return None


def to_decimal(value) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


class TelegaPay:
    def __init__(self, api_key: str, base_url: str = BASE_URL):
        self.api_key = (api_key or "").strip()
        self.base_url = base_url.rstrip("/")
        self._auth: tuple[str, str] | None = None

    # ------------------------------------------------------------ запросы

    def _headers(self, auth: tuple[str, str]) -> dict:
        name, template = auth
        return {name: template.format(key=self.api_key),
                "Content-Type": "application/json"}

    async def _post(self, path: str, payload: dict) -> dict:
        """POST с ключом. Первый раз перебирает способы авторизации."""
        if not self.api_key:
            raise PaymentError("не задан ключ TelegaPAY")

        variants = [self._auth] if self._auth else AUTH_HEADERS
        last = "шлюз не ответил"
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            for auth in variants:
                try:
                    async with session.post(
                        f"{self.base_url}{path}", json=payload,
                        headers=self._headers(auth),
                    ) as response:
                        body = await response.json(content_type=None)
                        if response.status in (401, 403):
                            last = f"HTTP {response.status}: ключ не принят"
                            continue
                        if response.status >= 400:
                            raise PaymentError(
                                f"HTTP {response.status}: {str(body)[:300]}"
                            )
                except aiohttp.ClientError as exc:
                    raise PaymentError(f"нет связи со шлюзом: {exc}") from exc
                except ValueError as exc:
                    raise PaymentError(f"шлюз ответил не JSON: {exc}") from exc

                self._auth = auth
                return body if isinstance(body, dict) else {"result": body}

        raise PaymentError(last)

    # ------------------------------------------------------------ методы

    async def get_methods(self, currency: str = "RUB", amount: str = "1000") -> dict:
        return await self._post("/get_methods",
                                {"currency": currency, "amount": amount})

    async def create_paylink(
        self, *, amount: Decimal, currency: str, order_id: str,
        description: str = "", user_id: str = "",
    ) -> Paylink:
        payload = {
            "amount": str(amount),
            "currency": currency,
            "order_id": order_id,
            "description": description or f"Пополнение {order_id}",
        }
        if user_id:
            payload["user_id"] = user_id

        body = await self._post("/create_paylink", payload)
        url = dig(body, LINK_KEYS)
        if not url:
            raise PaymentError(f"в ответе нет ссылки на оплату: {str(body)[:300]}")
        return Paylink(
            url=str(url),
            transaction_id=str(dig(body, ID_KEYS) or order_id),
            amount=to_decimal(dig(body, AMOUNT_KEYS)) or amount,
            raw=body,
        )

    async def check_status(self, transaction_id: str) -> Status:
        body = await self._post("/check_status", {"transaction_id": transaction_id})
        raw_status = str(dig(body, STATUS_KEYS) or "").strip().lower()
        return Status(
            raw_status=raw_status,
            paid=raw_status in PAID,
            failed=raw_status in FAILED,
            amount=to_decimal(dig(body, AMOUNT_KEYS)),
            raw=body,
        )

    async def cancel_payment(self, transaction_id: str) -> dict:
        return await self._post("/cancel_payment", {"transaction_id": transaction_id})

    # ------------------------------------------------------------ проверка

    async def healthcheck(self, currency: str = "RUB") -> dict:
        """Что именно отвечает шлюз — чтобы не гадать по документации."""
        steps: list[tuple[str, str]] = []
        if not self.api_key:
            return {"ok": False, "steps": [("Ключ", "❌ не задан")]}
        steps.append(("Ключ", f"✅ {self.api_key[:6]}…{self.api_key[-4:]}"))

        try:
            body = await self.get_methods(currency)
        except PaymentError as exc:
            steps.append(("Способы оплаты", f"❌ {exc}"))
            return {"ok": False, "steps": steps, "raw": {}}

        header = self._auth[0] if self._auth else "?"
        steps.append(("Авторизация", f"✅ заголовок {header}"))
        steps.append(("Способы оплаты", f"✅ ответ получен ({len(str(body))} симв.)"))
        return {"ok": True, "steps": steps, "raw": body}
