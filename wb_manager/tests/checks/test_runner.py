"""Запуск проверок: нет данных, ошибки WB, сломанная проверка, аномалии."""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

import pytest

from tests.checks.factory import NOW, bundle, feedback, orders, orders_between, stock
from wbm.analysis.anomalies import apply_anomalies, detect_anomalies
from wbm.checks import REGISTRY, run_checks
from wbm.checks.base import Check, CheckOutcome
from wbm.checks.thresholds import Thresholds
from wbm.domain.data import DataBundle, DataResult, Dataset
from wbm.domain.enums import CheckStatus, DatasetStatus


def test_all_ten_checks_are_registered_in_order() -> None:
    assert [c.id for c in REGISTRY] == [
        "stock_out",
        "orders_drop",
        "unanswered",
        "complaints",
        "returns",
        "unit_economics",
        "ads",
        "stale_stock",
        "card_quality",
        "deductions",
    ]


def test_nothing_loaded_means_no_data_not_crash() -> None:
    outcomes = run_checks(DataBundle(now=NOW))

    statuses = {o.check_id: o.status for o in outcomes}
    assert statuses.pop("unit_economics") is CheckStatus.NEEDS_COST
    assert set(statuses.values()) == {CheckStatus.NO_DATA}
    assert all(o.message for o in outcomes)


def test_failed_dataset_only_affects_checks_that_need_it() -> None:
    data = bundle(
        orders=DataResult.error("WB ответил HTTP 503 — сервис недоступен"),
        feedbacks=[feedback(1, 1, "Плохо")],
    )

    outcomes = {o.check_id: o for o in run_checks(data)}

    assert outcomes["stock_out"].status is CheckStatus.NO_DATA
    assert "заказы — WB ответил HTTP 503" in (outcomes["stock_out"].message or "")
    assert outcomes["unanswered"].status is CheckStatus.PROBLEMS


def test_needs_cost_message() -> None:
    outcome = {o.check_id: o for o in run_checks(bundle(finance=[]))}["unit_economics"]

    assert outcome.status is CheckStatus.NEEDS_COST
    assert "себестоимость" in (outcome.message or "")


class _Broken(Check):
    id = "broken"
    title = "Сломанная"
    requires: ClassVar[tuple[Dataset, ...]] = ()

    def run(self, data: DataBundle, thresholds: Thresholds) -> CheckOutcome:
        raise ZeroDivisionError


def test_broken_check_does_not_stop_others(caplog: pytest.LogCaptureFixture) -> None:
    outcomes = run_checks(bundle(feedbacks=[feedback(1, 1)]), checks=[_Broken, REGISTRY[2]])

    assert [o.status for o in outcomes] == [CheckStatus.ERROR, CheckStatus.PROBLEMS]
    assert "broken" in caplog.text


# ── аномалии ──────────────────────────────────────────────────────────────────


def test_order_gap_is_flagged_and_caveat_reaches_findings() -> None:
    # 10 заказов в день, кроме 3 дней подряд без заказов — похоже на сбой выгрузки.
    rows = []
    for day in range(30):
        if day in (5, 6, 7):
            continue
        rows += orders_between(1, 10, start_days_ago=day + 1, end_days_ago=day)
    data = bundle(orders=rows, stocks=[stock(1, 5)])

    anomalies = detect_anomalies(data)
    apply_anomalies(data, anomalies)

    assert [a.dataset for a in anomalies] == [Dataset.ORDERS]
    assert data.orders.status is DatasetStatus.ANOMALY
    assert "дн. подряд" in (data.orders.message or "")
    outcome = {o.check_id: o for o in run_checks(data)}["stock_out"]
    assert outcome.status is CheckStatus.PROBLEMS
    assert all(f.caveat and "сбой данных WB" in f.caveat for f in outcome.findings)


def test_empty_sales_finance_stocks_with_many_orders_are_suspicious() -> None:
    data = bundle(orders=orders(1, 40, days_ago=20), sales=[], finance=[], stocks=[])

    flagged = {a.dataset for a in detect_anomalies(data)}

    assert flagged == {Dataset.SALES, Dataset.FINANCE, Dataset.STOCKS}


def test_quiet_shop_is_not_an_anomaly() -> None:
    data = bundle(orders=orders(1, 3, days_ago=20), sales=[], finance=[], stocks=[])

    assert detect_anomalies(data) == []


def test_cost_prices_lookup_ignores_case_and_spaces() -> None:
    data = DataBundle(now=NOW, cost_prices={"art-1": Decimal(100)})

    assert data.cost_for(" ART-1 ") == Decimal(100)
    assert data.cost_for(None) is None
