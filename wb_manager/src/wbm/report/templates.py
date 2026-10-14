"""Тексты без Claude — из готовых полей проверки. Используются, если Claude недоступен,
отказал или написал число, которого нет в данных."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from wbm.checks.base import CheckOutcome, FactValue, Finding
from wbm.domain.enums import Severity

_UNITS = {"_руб": " ₽", "_процентов": " %", "_шт": " шт."}


def format_fact(key: str, value: FactValue) -> str:
    label = key
    unit = ""
    for suffix, sign in _UNITS.items():
        if key.endswith(suffix):
            label, unit = key[: -len(suffix)], sign
            break
    label = label.replace("_", " ")
    if isinstance(value, float):
        shown = f"{value:,.2f}".rstrip("0").rstrip(".").replace(",", " ").replace(".", ",")
    elif isinstance(value, int):
        shown = f"{value:,}".replace(",", " ")
    else:
        shown = value
    return f"{label}: {shown}{unit}"


def format_facts(facts: Mapping[str, FactValue]) -> str:
    return "; ".join(format_fact(k, v) for k, v in facts.items())


def template_finding_text(finding: Finding) -> str:
    parts = [f"{finding.reason} Что сделать: {finding.recommendation}"]
    if finding.facts:
        parts.append(f"Цифры: {format_facts(finding.facts)}.")
    if finding.caveat:
        parts.append(f"Важно: {finding.caveat}.")
    return " ".join(parts)


def template_summary(outcomes: Sequence[CheckOutcome], shop_name: str) -> str:
    counts = dict.fromkeys(Severity, 0)
    for outcome in outcomes:
        for finding in outcome.findings:
            counts[finding.severity] += 1
    total = sum(counts.values())
    if total == 0:
        return f"Магазин «{shop_name}»: по проверкам с данными серьёзных проблем не найдено."
    first = next(
        (f for o in outcomes for f in o.findings if f.severity is Severity.CRITICAL),
        None,
    )
    text = (
        f"Магазин «{shop_name}»: найдено проблем — {total} "
        f"(критично: {counts[Severity.CRITICAL]}, важно: {counts[Severity.IMPORTANT]}, "
        f"советов: {counts[Severity.ADVICE]})."
    )
    if first is not None:
        text += f" Начните с этого: {first.title}."
    return text
