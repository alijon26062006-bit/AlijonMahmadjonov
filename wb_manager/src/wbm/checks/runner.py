"""Запуск всех проверок. Одна сломанная проверка или пропавшие данные не роняют анализ."""

from __future__ import annotations

import logging
from dataclasses import replace

from wbm.checks.base import REGISTRY, Check, CheckOutcome
from wbm.checks.thresholds import Thresholds
from wbm.domain.data import DATASET_TITLES, DataBundle, Dataset
from wbm.domain.enums import CheckStatus, DatasetStatus

logger = logging.getLogger(__name__)


def run_checks(
    data: DataBundle,
    thresholds: Thresholds | None = None,
    checks: list[type[Check]] | None = None,
) -> list[CheckOutcome]:
    thresholds = thresholds or Thresholds()
    return [_run_one(check_class(), data, thresholds) for check_class in (checks or REGISTRY)]


def _run_one(check: Check, data: DataBundle, thresholds: Thresholds) -> CheckOutcome:
    if Dataset.COST_PRICES in check.requires and not data.cost_prices:
        return CheckOutcome(
            check.id,
            check.title,
            CheckStatus.NEEDS_COST,
            message="Нужна себестоимость: загрузите файл «артикул; себестоимость».",
        )
    missing = [
        d for d in check.requires if d is not Dataset.COST_PRICES and not data.result(d).usable
    ]
    if missing:
        details = "; ".join(_describe(data, d) for d in missing)
        return CheckOutcome(
            check.id, check.title, CheckStatus.NO_DATA, message=f"Нет данных: {details}"
        )

    try:
        outcome = check.run(data, thresholds)
    except Exception:
        logger.exception("Проверка %s упала", check.id)
        return CheckOutcome(
            check.id,
            check.title,
            CheckStatus.ERROR,
            message="Проверка не выполнилась из-за внутренней ошибки — мы уже видим её в логах.",
        )

    caveat = _anomaly_caveat(data, check)
    if caveat and outcome.findings:
        findings = tuple(
            replace(f, caveat="; ".join(c for c in (f.caveat, caveat) if c))
            for f in outcome.findings
        )
        outcome = replace(outcome, findings=findings)
    if caveat:
        message = "; ".join(m for m in (outcome.message, caveat) if m)
        outcome = replace(outcome, message=message)
    return outcome


def _describe(data: DataBundle, dataset: Dataset) -> str:
    result = data.result(dataset)
    reason = result.message or (
        "не загрузились" if result.status is DatasetStatus.ERROR else "не загружались"
    )
    return f"{DATASET_TITLES[dataset]} — {reason}"


def _anomaly_caveat(data: DataBundle, check: Check) -> str | None:
    parts = [
        f"{DATASET_TITLES[d]}: {data.result(d).message or 'данные выглядят подозрительно'}"
        for d in (*check.requires, *check.optional)
        if d is not Dataset.COST_PRICES and data.result(d).status is DatasetStatus.ANOMALY
    ]
    if not parts:
        return None
    return "Осторожно, возможен сбой данных WB — " + "; ".join(parts)
