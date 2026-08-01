"""Сервис расчёта стоимости доставки.

Ни одно число не захардкожено: тарифы, коэффициенты, сборы, скидки,
курсы валют и правила округления читаются из базы данных при каждом расчёте,
поэтому изменения из админ-панели применяются мгновенно.
"""
import json
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import (
    Calculation, Category, Coefficient, Currency, DeliveryType, ExchangeRate,
    ExtraService, Tariff,
)
from bot.repositories import SettingsRepo


@dataclass
class CalcResult:
    tariff: Tariff
    delivery_type: DeliveryType
    category: Category
    weight: Decimal
    volume: Decimal
    volumetric_weight: Decimal
    chargeable_weight: Decimal
    price_per_kg: Decimal
    base_cost: Decimal
    min_order_applied: bool
    lines: list[tuple[str, Decimal]] = field(default_factory=list)  # сборы/скидки/наценки
    total: Decimal = Decimal(0)
    currency_code: str = "USD"
    total_tjs: Decimal | None = None
    delivery_time: str | None = None


def _dec(value) -> Decimal:
    return Decimal(str(value))


def _apply_rounding(value: Decimal, mode: str, step: Decimal) -> Decimal:
    if mode == "none" or step <= 0:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    q = value / step
    rounding = {"up": ROUND_CEILING, "down": ROUND_FLOOR}.get(mode, ROUND_HALF_UP)
    return (q.quantize(Decimal("1"), rounding=rounding) * step).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


class CalculatorService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = SettingsRepo(session)

    async def _find_tariff(self, delivery_type_id: int, category_id: int) -> Tariff | None:
        """Сначала точный тариф (тип + категория), затем общий (тип, категория = NULL)."""
        stmt = select(Tariff).where(
            Tariff.is_active.is_(True),
            Tariff.delivery_type_id == delivery_type_id,
            Tariff.category_id == category_id,
        )
        tariff = await self.session.scalar(stmt)
        if tariff:
            return tariff
        stmt = select(Tariff).where(
            Tariff.is_active.is_(True),
            Tariff.delivery_type_id == delivery_type_id,
            Tariff.category_id.is_(None),
        )
        return await self.session.scalar(stmt)

    async def _coefficient(self, code: str, delivery_type_id: int | None = None,
                           category_id: int | None = None) -> Decimal | None:
        """Ищем наиболее специфичный активный коэффициент, затем глобальный."""
        stmt = select(Coefficient).where(
            Coefficient.is_active.is_(True), Coefficient.code == code
        )
        rows = list((await self.session.scalars(stmt)).all())

        for row in rows:  # специфичные (совпадение по типу доставки или категории)
            if (row.delivery_type_id and row.delivery_type_id == delivery_type_id) or \
               (row.category_id and row.category_id == category_id):
                return _dec(row.value)
        for row in rows:  # глобальные
            if row.delivery_type_id is None and row.category_id is None:
                return _dec(row.value)
        return None

    async def _rate_to_base(self, currency_code: str) -> Decimal | None:
        cur = await self.session.scalar(select(Currency).where(Currency.code == currency_code))
        if not cur:
            return None
        if cur.is_base:
            return Decimal(1)
        rate = await self.session.scalar(
            select(ExchangeRate).where(ExchangeRate.currency_id == cur.id)
            .order_by(ExchangeRate.updated_at.desc())
        )
        return _dec(rate.rate) if rate else None

    async def calculate(self, delivery_type_id: int, category_id: int,
                        weight: float, volume: float = 0,
                        user_id: int | None = None) -> CalcResult | None:
        tariff = await self._find_tariff(delivery_type_id, category_id)
        if not tariff:
            return None

        delivery_type = await self.session.get(DeliveryType, delivery_type_id)
        category = await self.session.get(Category, category_id)

        w, v = _dec(weight), _dec(volume)

        # 1. Объёмный вес
        vol_coef = await self._coefficient("volumetric", delivery_type_id=delivery_type_id)
        volumetric_weight = (v * vol_coef).quantize(Decimal("0.01")) if vol_coef and v > 0 else Decimal(0)

        # 2. Оплачиваемый вес = max(факт, объёмный, минимальный по тарифу)
        chargeable = max(w, volumetric_weight, _dec(tariff.min_weight or 0))

        # 3. Базовая стоимость (с учётом коэффициента плотного груза)
        price = _dec(tariff.price_per_kg)
        density = await self._coefficient("density", category_id=category_id)
        if density:
            price = price * density
        base = (price * chargeable).quantize(Decimal("0.01"))

        # 4. Минимальная стоимость заказа
        min_cost = _dec(tariff.min_order_cost or 0)
        min_applied = base < min_cost
        if min_applied:
            base = min_cost

        # 5. Доп. сборы, скидки, наценки
        stmt = select(ExtraService).where(ExtraService.is_active.is_(True))
        services = (await self.session.scalars(stmt)).all()
        lines: list[tuple[str, Decimal]] = []
        total = base
        for s in services:
            if s.delivery_type_id and s.delivery_type_id != delivery_type_id:
                continue
            if s.category_id and s.category_id != category_id:
                continue
            val = _dec(s.value)
            if s.calc_type == "percent":
                amount = (base * val / 100).quantize(Decimal("0.01"))
            elif s.calc_type == "per_kg":
                amount = (val * chargeable).quantize(Decimal("0.01"))
            else:
                amount = val
            if s.kind == "discount":
                amount = -amount
            lines.append((s.name, amount))
            total += amount
        total = max(total, Decimal(0))

        # 6. Округление по правилам из настроек
        mode = await self.settings.get("rounding_mode", "none")
        step = _dec(await self.settings.get("rounding_step", "1") or "1")
        total = _apply_rounding(total, mode or "none", step)

        # 7. Пересчёт в базовую валюту (TJS)
        total_tjs = None
        rate = await self._rate_to_base(tariff.currency_code)
        if rate and tariff.currency_code != "TJS":
            total_tjs = (total * rate).quantize(Decimal("0.01"))

        result = CalcResult(
            tariff=tariff, delivery_type=delivery_type, category=category,
            weight=w, volume=v, volumetric_weight=volumetric_weight,
            chargeable_weight=chargeable, price_per_kg=price.quantize(Decimal("0.01")),
            base_cost=base, min_order_applied=min_applied, lines=lines,
            total=total, currency_code=tariff.currency_code,
            total_tjs=total_tjs, delivery_time=tariff.delivery_time,
        )

        # 8. История расчётов
        self.session.add(Calculation(
            user_id=user_id, tariff_id=tariff.id,
            delivery_type=delivery_type.name if delivery_type else None,
            category=category.name if category else None,
            weight=float(w), volume=float(v),
            chargeable_weight=float(chargeable), total=float(total),
            currency_code=tariff.currency_code,
            details=json.dumps(
                {"lines": [(n, str(a)) for n, a in lines], "base": str(base)},
                ensure_ascii=False,
            ),
        ))
        await self.session.commit()
        return result
