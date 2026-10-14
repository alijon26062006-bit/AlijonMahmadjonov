"""Полный отчёт в PDF — из сохранённого в базе анализа (подходит и для истории)."""

from __future__ import annotations

import io
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from wbm.db.models import AnalysisRun, CheckResult, Finding
from wbm.domain.enums import SEVERITY_TITLES, CheckStatus, Severity
from wbm.report.templates import format_facts

FONT_DIRS = (
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/dejavu",
    "/usr/local/share/fonts",
    "/Library/Fonts",
    "C:/Windows/Fonts",
)
_SEVERITY_COLORS = {
    Severity.CRITICAL: colors.HexColor("#b42318"),
    Severity.IMPORTANT: colors.HexColor("#b54708"),
    Severity.ADVICE: colors.HexColor("#175cd3"),
}
MAX_PRODUCT_ROWS = 30


class PdfFontError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _fonts() -> tuple[str, str]:
    for directory in FONT_DIRS:
        regular, bold = Path(directory) / "DejaVuSans.ttf", Path(directory) / "DejaVuSans-Bold.ttf"
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont("WBM", str(regular)))
            pdfmetrics.registerFont(TTFont("WBM-Bold", str(bold)))
            return "WBM", "WBM-Bold"
    raise PdfFontError("Нет шрифта DejaVuSans с кириллицей (пакет fonts-dejavu-core)")


def _styles() -> dict[str, ParagraphStyle]:
    regular, bold = _fonts()
    base = ParagraphStyle("base", fontName=regular, fontSize=10, leading=14)
    return {
        "base": base,
        "small": ParagraphStyle("small", parent=base, fontSize=8, leading=10),
        "muted": ParagraphStyle("muted", parent=base, textColor=colors.HexColor("#667085")),
        "h1": ParagraphStyle(
            "h1", parent=base, fontName=bold, fontSize=17, leading=22, spaceAfter=4
        ),
        "h2": ParagraphStyle(
            "h2", parent=base, fontName=bold, fontSize=13, leading=18, spaceBefore=10
        ),
        "h3": ParagraphStyle(
            "h3", parent=base, fontName=bold, fontSize=11, leading=15, spaceBefore=8
        ),
    }


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def build_pdf(run: AnalysisRun, shop_name: str) -> bytes:
    styles = _styles()
    story: list[Any] = [
        _p("Отчёт об анализе магазина", styles["h1"]),
        _p(
            f"Магазин: {shop_name} · период: {run.period_days} дней · "
            f"дата: {(run.finished_at or run.created_at):%d.%m.%Y %H:%M} (UTC)",
            styles["muted"],
        ),
        Spacer(1, 4 * mm),
    ]
    summary_text = (run.summary or {}).get("summary_text")
    if isinstance(summary_text, str) and summary_text:
        story += [_p(summary_text, styles["base"]), Spacer(1, 2 * mm)]

    findings = _sorted_findings(run.checks)
    for severity in (Severity.CRITICAL, Severity.IMPORTANT, Severity.ADVICE):
        items = [f for f in findings if f.severity == severity]
        if not items:
            continue
        heading = ParagraphStyle(
            f"h2-{severity}", parent=styles["h2"], textColor=_SEVERITY_COLORS[severity]
        )
        story.append(_p(f"{SEVERITY_TITLES[severity]} — {len(items)}", heading))
        for finding in items:
            story += _finding_block(finding, styles)

    skipped = [
        c for c in run.checks if c.status != CheckStatus.PROBLEMS and c.status != CheckStatus.OK
    ]
    passed = [c for c in run.checks if c.status == CheckStatus.OK]
    if passed:
        story.append(_p("Без проблем", styles["h2"]))
        story += [_p(f"✓ {c.title}", styles["base"]) for c in passed]
    if skipped:
        story.append(_p("Не проверено", styles["h2"]))
        story += [_p(f"• {c.title}: {c.message or ''}", styles["base"]) for c in skipped]

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title="Отчёт об анализе магазина",
    )
    document.build(story)
    return buffer.getvalue()


def _sorted_findings(checks: Sequence[CheckResult]) -> list[Finding]:
    order = {Severity.CRITICAL: 0, Severity.IMPORTANT: 1, Severity.ADVICE: 2}
    items = [(check.position, f) for check in checks for f in check.findings]
    items.sort(
        key=lambda pair: (order.get(Severity(pair[1].severity), 3), pair[0], pair[1].position)
    )
    return [f for _, f in items]


def _finding_block(finding: Finding, styles: dict[str, ParagraphStyle]) -> list[Any]:
    block: list[Any] = [_p(finding.title, styles["h3"])]
    text = finding.text or f"{finding.reason} Что сделать: {finding.recommendation}"
    block.append(_p(text, styles["base"]))
    if finding.facts:
        block.append(_p(f"Цифры: {format_facts(finding.facts)}", styles["muted"]))
    if finding.caveat:
        block.append(_p(f"Важно: {finding.caveat}", styles["muted"]))
    if finding.products:
        block.append(Spacer(1, 2 * mm))
        block.append(_products_table(finding.products, styles))
    return block


def _products_table(products: list[dict[str, Any]], styles: dict[str, ParagraphStyle]) -> Table:
    rows = [
        [_p("Товар", styles["small"]), _p("Артикул", styles["small"]), _p("Цифры", styles["small"])]
    ]
    for product in products[:MAX_PRODUCT_ROWS]:
        metrics = product.get("metrics") or {}
        rows.append(
            [
                _p(str(product.get("name") or product.get("nm_id") or "—"), styles["small"]),
                _p(str(product.get("vendor_code") or "—"), styles["small"]),
                _p(format_facts(metrics), styles["small"]),
            ]
        )
    if len(products) > MAX_PRODUCT_ROWS:
        rows.append([_p(f"… и ещё {len(products) - MAX_PRODUCT_ROWS}", styles["small"]), "", ""])
    table = Table(rows, colWidths=[55 * mm, 35 * mm, 90 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f4f7")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d0d5dd")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table
