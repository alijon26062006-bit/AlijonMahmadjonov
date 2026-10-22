"""Конструктор: боти шарик молро аз платформа бо нархи яклухт мегирад.

Харидори боти шарик ба шарик пул медиҳад (ба реквизитҳои шарик). Ҳар фармоиш
дар боти шарик аз ҳисоби шарик дар боти асосӣ нархи яклухтро мегирад ва
тавассути ҳамон роҳи иҷрои боти асосӣ (FireLoot / Donatix / дастӣ) меравад.

    нархи яклухт = нархи харид × курс × (1 + наценкаи конструктор)
    нархи фурӯш  = нархи яклухт × (1 + наценкаи шарик)   — ё нархи дастии шарик
"""

from __future__ import annotations

import hashlib
import logging
import time
from decimal import ROUND_CEILING, Decimal, InvalidOperation

from . import costs
from .db import Database, DuplicateRequest, NotEnoughMoney
from .supplier import CheckResult, OrderResult

log = logging.getLogger(__name__)

WHOLESALE_MARKUP_KEY = "constructor_markup_percent"
DEFAULT_WHOLESALE_MARKUP = 10.0
PARTNER_MARKUP_KEY = "partner_markup_percent"
DEFAULT_PARTNER_MARKUP = 15.0
LOW_BALANCE_KEY = "low_balance_dirams"
DEFAULT_LOW_BALANCE = 5000            # 50 сомонӣ
LOW_WARN_EVERY = 6 * 3600
EMPTY_WARN_EVERY = 30 * 60

STATUS = {"new": "processing", "sent": "processing", "done": "completed", "rejected": "failed"}


def _percent(db: Database, key: str, default: float) -> float:
    try:
        value = float(db.setting(key) or default)
    except ValueError:
        return default
    return value if 0 <= value <= 500 else default


def wholesale_markup(main_db: Database) -> float:
    return _percent(main_db, WHOLESALE_MARKUP_KEY, DEFAULT_WHOLESALE_MARKUP)


def partner_markup(tenant_db: Database) -> float:
    return _percent(tenant_db, PARTNER_MARKUP_KEY, DEFAULT_PARTNER_MARKUP)


def wholesale_price(main_db: Database, main_row) -> int | None:
    """Нархи яклухт дар дирам. Моли хомӯш ё бе нархи харид — None (намефурӯшем)."""
    if main_row is None or not main_row["active"]:
        return None
    return costs.api_price(main_row["cost"], costs.usd_rate(main_db), wholesale_markup(main_db))


def retail_price(wholesale: int, markup: float) -> int:
    """Нархи фурӯши шарик: яклухт + наценка, ба боло то 0.50 сомонӣ."""
    try:
        raw = Decimal(int(wholesale)) * (Decimal(100) + Decimal(str(markup))) / Decimal(100)
    except InvalidOperation:
        return int(wholesale)
    halves = (raw / Decimal(50)).to_integral_value(rounding=ROUND_CEILING)
    return int(halves * 50)


def reprice_tenant(main_db: Database, tenant_db: Database) -> dict[str, int]:
    """Нархҳои боти шарикро аз нархи яклухт нав мекунад.

    Молҳои нави платформа (custom) ба боти шарик хомӯш илова мешаванд.
    Моле, ки платформа намефурӯшад, дар боти шарик худкор пинҳон мешавад
    ва вақте боз пайдо шавад, худкор бармегардад.
    """
    added = 0
    for row in main_db.all_products():
        if row["custom"] and tenant_db.product(row["code"]) is None:
            group = main_db.group(row["group_code"]) if row["group_code"] else None
            if group is not None:
                tenant_db.add_custom_group(group["code"], group["category"], group["title"])
            added += tenant_db.add_custom_products([{
                "code": row["code"], "category": row["category"], "title": row["title"],
                "amount": row["amount"], "price": row["price"], "cost": None,
                "group": row["group_code"], "sku": row["sku"], "kind": row["kind"],
            }])

    markup = partner_markup(tenant_db)
    available = hidden = 0
    for row in tenant_db.all_products():
        price = wholesale_price(main_db, main_db.product(row["code"]))
        tenant_db.set_wholesale(
            row["code"], price,
            auto_price=retail_price(price, markup) if price is not None else None,
            available=price is not None,
        )
        if price is None:
            hidden += 1
        else:
            available += 1
    return {"available": available, "hidden": hidden, "added": added}


class WholesaleSupplier:
    """«Таъминкунанда»-и боти шарик — худи платформа.

    Фармоиш ба базаи асосӣ ҳамчун фармоиши шарик навишта мешавад (бо Idempotency-Key),
    пулро аз ҳисоби шарик мегирад ва бо роҳи боти асосӣ иҷро мешавад.
    """

    name = "wholesale"
    idempotent = True

    def __init__(self, platform, tenant_id: int, partner_id: int, tenant_db: Database) -> None:
        self.platform = platform
        self.tenant_id = tenant_id
        self.partner_id = partner_id
        self.tenant_db = tenant_db

    def for_kind(self, kind: str, sku: str = "") -> "WholesaleSupplier | None":
        return None if kind == "manual" else self

    async def check(self, *, kind: str, sku: str, target: str, amount: int,
                    server: str = "") -> CheckResult:
        return await self.platform.supplier.check(
            kind=kind, sku=sku, target=target, amount=amount, server=server
        )

    async def place_order(self, **kwargs) -> OrderResult:      # pragma: no cover
        return OrderResult(ok=False, code="use_place_for", error="place_for")

    async def place_for(self, row, target: str, server: str, ref: str) -> OrderResult:
        """Фармоиши боти шарикро дар платформа мекушояд ва пули яклухтро мегирад."""
        from .fulfillment import deliver_in_background

        main = self.platform
        product = main.db.product(row["product_code"])
        price = wholesale_price(main.db, product)
        if price is None:
            return OrderResult(ok=False, code="product_not_found",
                               error="Ин мол ҳоло дастрас нест")
        body = f"{row['product_code']}|{target}|{server}"
        try:
            order_id = main.db.create_order(
                user_id=self.partner_id, product_code=product["code"],
                category=product["category"], title=product["title"], price=price,
                target=target + (f" ({server})" if server else ""),
                nickname=row["nickname"], sku=product["sku"] or "",
                kind=product["kind"] or "game", source="tenant",
                api_key_id=-self.tenant_id,
                idem=(ref, hashlib.sha256(body.encode()).hexdigest()),
            )
        except DuplicateRequest as dup:
            # Такрор (масалан, пас аз азнавоғозкунӣ): ҳамон фармоиш, пул дубора намеравад.
            if not dup.same_body:
                return OrderResult(ok=False, uncertain=True, error="duplicate ref")
            existing = main.db.order(dup.order_id)
            return OrderResult(ok=True, external_id=f"W{dup.order_id}",
                               status=STATUS.get(existing["status"], "processing"))
        except NotEnoughMoney:
            await self._warn_empty()
            # Харидор сабаби дохилиро намебинад; шарик огоҳӣ гирифт.
            return OrderResult(ok=False, code="wholesale_balance",
                               error="Фармоиш ҳоло иҷро намешавад")

        # Иҷрои фармоиши платформа бо забон ва контексти боти асосӣ, на боти шарик.
        from .tenants import bot_context

        with bot_context(main.cfg.lang, 0):
            deliver_in_background(main.bot, main.db, main.cfg, main.supplier, order_id)
        await self._warn_low()
        return OrderResult(ok=True, external_id=f"W{order_id}", status="processing")

    def _main_order(self, external_id: str):
        if not str(external_id).startswith("W"):
            return None
        try:
            return self.platform.db.order(int(str(external_id)[1:]))
        except ValueError:
            return None

    async def order_status(self, external_id: str, *, by_external: bool = False) -> OrderResult:
        if by_external:
            return OrderResult(ok=False, code="lookup_unsupported", error="lookup_unsupported")
        row = self._main_order(external_id)
        if row is None or row["user_id"] != self.partner_id:
            return OrderResult(ok=False, code="order_not_found", error="order_not_found")
        status = STATUS.get(row["status"], "processing")
        return OrderResult(ok=True, external_id=external_id, status=status,
                           error="Таъминкунанда фармоишро иҷро накард" if status == "failed" else None)

    async def wait_until_done(self, external_id: str, *, by_external: bool = False,
                              max_wait: int = 240, interval: float = 3) -> OrderResult:
        import asyncio

        waited = 0.0
        last = OrderResult(ok=False, error="timeout")
        while waited < max_wait:
            result = await self.order_status(external_id)
            if result.ok:
                last = result
                if result.status in ("completed", "failed"):
                    return result
            await asyncio.sleep(interval)
            waited += interval
        return last

    async def balance(self) -> dict:
        user = self.platform.db.user(self.partner_id)
        return {"ok": True, "balance": f"{(user.balance if user else 0) / 100:.2f}",
                "currency": "TJS"}

    async def products(self) -> dict:
        return {}

    async def close(self) -> None:
        return None

    # ── огоҳиҳо ба шарик ──────────────────────────────────────────────
    async def _notify_partner(self, text: str) -> None:
        try:
            await self.platform.bot.send_message(self.partner_id, text)
        except Exception as exc:
            log.info("Огоҳӣ ба шарик %s нарасид: %s", self.partner_id, exc)

    def _throttled(self, key: str, every: int) -> bool:
        last = self.tenant_db.setting(key)
        now = time.time()
        try:
            if last and now - float(last) < every:
                return True
        except ValueError:
            pass
        self.tenant_db.set_setting(key, str(now))
        return False

    async def _warn_low(self) -> None:
        from .i18n import texts

        user = self.platform.db.user(self.partner_id)
        try:
            limit = int(self.tenant_db.setting(LOW_BALANCE_KEY) or DEFAULT_LOW_BALANCE)
        except ValueError:
            limit = DEFAULT_LOW_BALANCE
        if user is None or user.balance >= limit or self._throttled("low_warned_at", LOW_WARN_EVERY):
            return
        await self._notify_partner(texts.partner_low_balance(user.balance))

    async def _warn_empty(self) -> None:
        from .i18n import texts

        if self._throttled("empty_warned_at", EMPTY_WARN_EVERY):
            return
        user = self.platform.db.user(self.partner_id)
        await self._notify_partner(texts.partner_empty_balance(user.balance if user else 0))
