"""Проверки 6–10 на фиктивных данных."""

from __future__ import annotations

from decimal import Decimal

from tests.checks.factory import (
    ad_day,
    ago,
    bundle,
    finance,
    nm_ids,
    only,
    orders,
    product,
    stock,
    storage_cost,
    supply,
)
from wbm.checks.c06_unit_economics import UnitEconomicsCheck
from wbm.checks.c07_ads import AdsCheck
from wbm.checks.c08_stale_stock import StaleStockCheck
from wbm.checks.c09_card_quality import CardQualityCheck
from wbm.checks.c10_deductions import DeductionsCheck
from wbm.checks.thresholds import Thresholds
from wbm.domain.data import Campaign, CardError, Characteristic, DataResult, FinanceKind
from wbm.domain.enums import CheckStatus, Severity

T = Thresholds()
SALE, RETURN, LOGISTICS = FinanceKind.SALE, FinanceKind.RETURN, FinanceKind.LOGISTICS

# ── 6. Юнит-экономика ─────────────────────────────────────────────────────────


def test_losing_and_thin_margin_products() -> None:
    data = bundle(
        finance=[
            # товар 1: 10 шт., к перечислению 5000, логистика 1500 → минус при себестоимости 400
            finance(1, SALE, quantity=10, retail=8000, payout=5000),
            finance(1, LOGISTICS, logistics=1500),
            # товар 2: 10 шт., 1 возврат; маржа ~2 %
            finance(2, SALE, quantity=10, retail=10000, payout=7000),
            finance(2, RETURN, quantity=1, retail=1000, payout=700),
            finance(2, LOGISTICS, logistics=400),
            # товар 3: хорошая прибыль
            finance(3, SALE, quantity=10, retail=10000, payout=8000),
        ],
        cost_prices={"art-1": Decimal(400), "art-2": Decimal(650), "art-3": Decimal(200)},
    )

    outcome = UnitEconomicsCheck().run(data, T)

    losing = only(outcome, Severity.CRITICAL)[0]
    assert nm_ids(losing) == [1]
    metrics = losing.products[0].metrics
    assert metrics["прибыль_руб"] == -500.0  # 5000 − 1500 − 4000
    assert metrics["прибыль_на_штуку_руб"] == -50.0
    assert metrics["логистика_руб"] == 1500.0
    thin = only(outcome, Severity.ADVICE)[0]
    assert nm_ids(thin) == [2]
    assert thin.products[0].metrics["продано_шт"] == 9
    assert thin.products[0].metrics["прибыль_руб"] == 50.0  # 6300 − 400 − 5850
    assert outcome.message is None


def test_unit_economics_partial_and_unmatched_cost() -> None:
    rows = [finance(1, SALE, quantity=2, retail=2000, payout=1500), finance(2, SALE, quantity=1)]

    partial = UnitEconomicsCheck().run(bundle(finance=rows, cost_prices={"art-1": Decimal(100)}), T)
    assert partial.status is CheckStatus.OK
    assert partial.message is not None
    assert "ART-2" in partial.message

    unmatched = UnitEconomicsCheck().run(
        bundle(finance=rows, cost_prices={"другой": Decimal(1)}), T
    )
    assert unmatched.status is CheckStatus.NEEDS_COST


# ── 7. Реклама ────────────────────────────────────────────────────────────────


def test_ads_without_orders_and_high_drr() -> None:
    data = bundle(
        campaign_stats=[
            ad_day(1, 1500),
            ad_day(1, 700),  # 2200 ₽ без заказов
            ad_day(2, 4000, orders=5, orders_sum=10000),  # ДРР 40 %
            ad_day(3, 2500, orders=10, orders_sum=10000),  # ДРР 25 %
            ad_day(4, 300, orders=1, orders_sum=500),  # мало расхода для выводов
            ad_day(5, 500),  # мало расхода без заказов
            ad_day(6, 9000, days_ago=45),  # вне периода
        ],
        campaigns=[Campaign(1, "Платья поиск"), Campaign(2, "Авто платья")],
    )

    outcome = AdsCheck().run(data, T)

    critical = only(outcome, Severity.CRITICAL)
    wasted = next(f for f in critical if "без заказов" in f.title)
    assert wasted.facts["расход_без_заказов_руб"] == 2200.0
    assert "Платья поиск" in str(wasted.facts["кампании"])
    drr = next(f for f in critical if "ДРР" in f.title)
    assert drr.facts["дрр_процентов"] == 40.0
    assert "Авто платья" in drr.title
    important = only(outcome, Severity.IMPORTANT)
    assert [f.facts["id_кампании"] for f in important] == [3]


def test_ads_empty_stats() -> None:
    assert AdsCheck().run(bundle(campaign_stats=[]), T).status is CheckStatus.OK


# ── 8. Залежавшийся товар ─────────────────────────────────────────────────────


def test_stale_stock_with_storage_cost() -> None:
    data = bundle(
        stocks=[stock(1, 50), stock(2, 5), stock(3, 10)],
        orders=orders(3, 5, days_ago=10),
        paid_storage=[storage_cost(1, 400), storage_cost(1, 300), storage_cost(2, 50)],
    )

    outcome = StaleStockCheck().run(data, T)

    expensive = only(outcome, Severity.IMPORTANT)[0]
    assert nm_ids(expensive) == [1]
    assert expensive.facts["хранение_за_30_дней_руб"] == 700.0
    assert nm_ids(only(outcome, Severity.ADVICE)[0]) == [2]
    assert outcome.message is None


def test_stale_stock_without_storage_report() -> None:
    data = bundle(stocks=[stock(1, 50)], orders=[], paid_storage=DataResult.error("HTTP 500"))

    outcome = StaleStockCheck().run(data, T)

    assert nm_ids(only(outcome, Severity.ADVICE)[0]) == [1]
    assert outcome.message is not None


# ── 9. Карточки ───────────────────────────────────────────────────────────────


def test_card_quality() -> None:
    data = bundle(
        products=[
            product(
                1,
                characteristics=[
                    Characteristic("Состав", None, required=True),
                    Characteristic("Цвет", "красный"),
                    Characteristic("Сезон", ""),
                ],
            ),
            product(2, description="Коротко", photos=1),
            product(3),
        ],
        card_errors=[CardError(vendor_code="ART-9", errors=("Не указан ТНВЭД",))],
    )

    outcome = CardQualityCheck().run(data, T)

    errors = only(outcome, Severity.CRITICAL)[0]
    assert errors.products[0].metrics["ошибки"] == "Не указан ТНВЭД"
    required = only(outcome, Severity.IMPORTANT)[0]
    assert required.products[0].metrics["пустые_обязательные"] == "Состав"
    advice_titles = {f.title.split(":")[0]: nm_ids(f) for f in only(outcome, Severity.ADVICE)}
    assert advice_titles == {
        "Много пустых характеристик": [1],
        "Короткое описание": [2],
        "Мало фото": [2],
    }


def test_card_quality_without_error_list() -> None:
    outcome = CardQualityCheck().run(
        bundle(products=[product(1)], card_errors=DataResult.error("HTTP 429")), T
    )

    assert outcome.status is CheckStatus.OK
    assert outcome.message is not None


# ── 10. Подозрительные удержания ──────────────────────────────────────────────


def test_penalties_logistics_and_acceptance() -> None:
    logistics = [
        finance(nm, LOGISTICS, quantity=1, logistics=60) for nm in (1, 2, 3) for _ in range(3)
    ]
    logistics += [finance(4, LOGISTICS, quantity=1, logistics=300) for _ in range(3)]
    data = bundle(
        finance=[
            *logistics,
            finance(None, FinanceKind.PENALTY, penalty=1000, comment="Неверные габариты"),
            finance(None, FinanceKind.PENALTY, penalty=500, comment="Неверные габариты"),
            finance(None, FinanceKind.DEDUCTION, deduction=200, comment="Хранение сверх нормы"),
        ],
        supplies=[supply(1, planned=100, accepted=95), supply(2, planned=50, accepted=50)],
    )

    outcome = DeductionsCheck().run(data, T)

    penalties = next(f for f in outcome.findings if "Штрафы" in f.title)
    assert penalties.facts["сумма_штрафов_руб"] == 1500.0
    assert "Неверные габариты — 2" in str(penalties.facts["причины"])
    expensive = next(f for f in outcome.findings if "Логистика" in f.title)
    assert nm_ids(expensive) == [4]
    assert expensive.products[0].metrics["логистика_на_единицу_руб"] == 300.0
    acceptance = next(f for f in outcome.findings if "приёмке" in f.title)
    assert acceptance.facts["не_хватает_шт"] == 5
    assert any("удержания" in f.title for f in only(outcome, Severity.ADVICE))
    assert outcome.message is not None  # без прошлых остатков пропажу не проверить


def test_missing_stock_compared_to_previous_analysis() -> None:
    data = bundle(
        finance=[],
        previous_stocks=[stock(1, 100), stock(2, 50)],
        stocks=[stock(1, 80), stock(2, 40)],
        orders=orders(1, 10, days_ago=6) + orders(2, 10, days_ago=6),
        supplies=[supply(1, planned=5, accepted=5, days_ago=3)],
    )
    data.previous_stocks_at = ago(7)

    outcome = DeductionsCheck().run(data, T)

    missing = next(f for f in outcome.findings if "пропал" in f.title)
    assert nm_ids(missing) == [1]  # 100 + 5 − 10 − 80 = 15 шт. не объяснено
    assert missing.products[0].metrics["не_объяснено_шт"] == 15
    assert missing.caveat is not None
    assert outcome.message is None


def test_deductions_clean_report() -> None:
    outcome = DeductionsCheck().run(bundle(finance=[], supplies=[]), T)

    assert outcome.status is CheckStatus.OK
