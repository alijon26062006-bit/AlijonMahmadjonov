"""Перевод результатов анализа в записи базы данных."""

from __future__ import annotations

from collections.abc import Iterable

from wbm.checks.base import SEVERITY_ORDER, CheckOutcome
from wbm.db.models import CheckResult, Finding, RunDataset
from wbm.domain.data import DataBundle, Dataset
from wbm.domain.enums import CheckStatus, Severity


def dataset_records(data: DataBundle) -> list[RunDataset]:
    records = []
    for dataset in Dataset:
        if dataset is Dataset.COST_PRICES:
            records.append(
                RunDataset(
                    dataset=dataset.value,
                    status="ok" if data.cost_prices else "skipped",
                    rows=len(data.cost_prices),
                )
            )
            continue
        result = data.result(dataset)
        records.append(
            RunDataset(
                dataset=dataset.value,
                status=result.status.value,
                rows=len(result.rows),
                message=result.message,
            )
        )
    return records


def check_records(outcomes: Iterable[CheckOutcome]) -> list[CheckResult]:
    return [
        CheckResult(
            check_id=outcome.check_id,
            title=outcome.title[:255],
            status=outcome.status.value,
            position=position,
            message=outcome.message,
            findings=[
                Finding(
                    severity=finding.severity.value,
                    position=index,
                    title=finding.title[:255],
                    products=[p.as_dict() for p in finding.products],
                    facts=dict(finding.facts),
                    reason=finding.reason,
                    recommendation=finding.recommendation,
                    caveat=finding.caveat,
                )
                for index, finding in enumerate(outcome.findings)
            ],
        )
        for position, outcome in enumerate(outcomes)
    ]


def summary(outcomes: Iterable[CheckOutcome]) -> dict[str, object]:
    """Короткие итоги для списка анализов и Telegram."""
    items = list(outcomes)
    counts = {severity.value: 0 for severity in SEVERITY_ORDER}
    for outcome in items:
        for finding in outcome.findings:
            counts[finding.severity.value] += 1
    return {
        "problems": counts,
        "checks_without_data": [o.check_id for o in items if o.status is CheckStatus.NO_DATA],
        "needs_cost": any(o.status is CheckStatus.NEEDS_COST for o in items),
        "worst": next(
            (
                s.value
                for s in (Severity.CRITICAL, Severity.IMPORTANT, Severity.ADVICE)
                if counts[s.value]
            ),
            None,
        ),
    }
