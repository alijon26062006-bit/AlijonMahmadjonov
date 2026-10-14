"""Сборка текста отчёта: Claude, если доступен и честен с цифрами, иначе — шаблоны."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol

from wbm.checks.base import CheckOutcome
from wbm.domain.enums import SEVERITY_TITLES, CheckStatus, Severity
from wbm.report.llm import LLMReport, ReportWriterError
from wbm.report.payload import build_payload, finding_payload, iter_findings
from wbm.report.templates import format_facts, template_finding_text, template_summary
from wbm.report.validate import allowed_numbers, unknown_numbers

logger = logging.getLogger(__name__)


class ReportWriter(Protocol):
    async def write(self, payload: dict[str, object]) -> LLMReport: ...


@dataclass(slots=True)
class ReportText:
    summary: str
    texts: dict[str, str]
    """Текст по ключу проблемы (c{проверка}f{проблема})."""
    source: Literal["claude", "template", "mixed"]
    issues: list[str] = field(default_factory=list)
    """Что пошло не так с текстом Claude — для логов и диагностики."""


async def generate_report(
    outcomes: Sequence[CheckOutcome],
    *,
    shop_name: str,
    period_days: int,
    writer: ReportWriter | None,
) -> ReportText:
    findings = iter_findings(outcomes)
    templates = {ref.key: template_finding_text(f) for ref, f in findings}
    fallback = ReportText(template_summary(outcomes, shop_name), templates, "template")
    if writer is None or not findings:
        return fallback

    payload = build_payload(outcomes, shop_name=shop_name, period_days=period_days)
    try:
        written = await writer.write(payload)
    except ReportWriterError as exc:
        logger.warning("Текст отчёта по шаблонам: %s", exc)
        fallback.issues.append(str(exc))
        return fallback

    issues: list[str] = []
    by_key = {item.key: item.text.strip() for item in written.findings}
    texts: dict[str, str] = {}
    for ref, finding in findings:
        text = by_key.get(ref.key, "")
        if not text:
            issues.append(f"{ref.key}: Claude не написал текст")
            texts[ref.key] = templates[ref.key]
            continue
        invented = unknown_numbers(text, allowed_numbers(finding_payload(ref, finding)))
        if invented:
            issues.append(f"{ref.key}: числа не из данных: {', '.join(invented)}")
            texts[ref.key] = templates[ref.key]
            continue
        texts[ref.key] = text

    summary = written.summary.strip()
    invented = unknown_numbers(summary, allowed_numbers(payload))
    if not summary or invented:
        issues.append(
            f"итог: числа не из данных: {', '.join(invented)}" if invented else "итог пуст"
        )
        summary = fallback.summary

    for issue in issues:
        logger.warning("Текст Claude отклонён — %s", issue)
    used_claude = len(texts) - sum(1 for k, t in texts.items() if t == templates[k])
    source: Literal["claude", "template", "mixed"]
    if not issues:
        source = "claude"
    elif used_claude == 0 and summary == fallback.summary:
        source = "template"
    else:
        source = "mixed"
    return ReportText(summary, texts, source, issues)


def render_markdown(outcomes: Sequence[CheckOutcome], report: ReportText) -> str:
    """Полный отчёт текстом (для истории анализов и выгрузки)."""
    lines = ["# Отчёт об анализе магазина", "", report.summary, ""]
    for severity in (Severity.CRITICAL, Severity.IMPORTANT, Severity.ADVICE):
        items = [(ref, f) for ref, f in iter_findings(outcomes) if f.severity is severity]
        if not items:
            continue
        lines += [f"## {SEVERITY_TITLES[severity]}", ""]
        for ref, finding in items:
            lines += [f"### {finding.title}", "", report.texts.get(ref.key, ""), ""]
            if finding.facts:
                lines += [f"Цифры: {format_facts(finding.facts)}", ""]
            for product in finding.products[:20]:
                name = product.name or product.vendor_code or product.nm_id
                lines.append(
                    f"- {name} (арт. {product.vendor_code}): {format_facts(product.metrics)}"
                )
            if finding.products:
                lines.append("")
    skipped = [
        o
        for o in outcomes
        if o.status in (CheckStatus.NO_DATA, CheckStatus.NEEDS_COST, CheckStatus.ERROR)
    ]
    if skipped:
        lines += ["## Не проверено", ""]
        lines += [f"- {o.title}: {o.message}" for o in skipped]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
