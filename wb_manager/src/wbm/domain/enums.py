"""Перечисления, общие для проверок, базы и отчёта."""

from __future__ import annotations

from enum import StrEnum


class Severity(StrEnum):
    CRITICAL = "critical"
    IMPORTANT = "important"
    ADVICE = "advice"


SEVERITY_TITLES = {
    Severity.CRITICAL: "Критично",
    Severity.IMPORTANT: "Важно",
    Severity.ADVICE: "Совет",
}


class CheckStatus(StrEnum):
    PROBLEMS = "problems"
    OK = "ok"
    NO_DATA = "no_data"
    NEEDS_COST = "needs_cost"
    ERROR = "error"


class DatasetStatus(StrEnum):
    OK = "ok"
    EMPTY = "empty"
    ERROR = "error"
    ANOMALY = "anomaly"
    SKIPPED = "skipped"
