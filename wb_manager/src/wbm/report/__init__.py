"""Текст отчёта: Claude пересказывает готовые цифры, шаблоны — запасной вариант."""

from wbm.report.llm import ClaudeReportWriter, ReportWriterError
from wbm.report.service import ReportText, ReportWriter, generate_report, render_markdown

__all__ = [
    "ClaudeReportWriter",
    "ReportText",
    "ReportWriter",
    "ReportWriterError",
    "generate_report",
    "render_markdown",
]
