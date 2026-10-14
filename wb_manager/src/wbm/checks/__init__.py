"""Проверки магазина. Импорт модулей регистрирует проверки в REGISTRY по порядку."""

from wbm.checks import (  # noqa: F401 — регистрация проверок
    c01_stock_out,
    c02_orders_drop,
    c03_unanswered,
    c04_complaints,
    c05_returns,
    c06_unit_economics,
    c07_ads,
    c08_stale_stock,
    c09_card_quality,
    c10_deductions,
)
from wbm.checks.base import REGISTRY, AffectedProduct, Check, CheckOutcome, Finding
from wbm.checks.runner import run_checks
from wbm.checks.thresholds import Thresholds

__all__ = [
    "REGISTRY",
    "AffectedProduct",
    "Check",
    "CheckOutcome",
    "Finding",
    "Thresholds",
    "run_checks",
]
