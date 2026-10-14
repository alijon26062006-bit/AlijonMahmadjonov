"""Текст отчёта: Claude используется, только если не придумывает цифры."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import anthropic
import httpx2
import pytest

from tests.checks.factory import bundle, feedback, orders, stock
from wbm.checks import run_checks
from wbm.checks.base import CheckOutcome
from wbm.report import ClaudeReportWriter, generate_report, render_markdown
from wbm.report.llm import LLMReport, ReportWriterError
from wbm.report.payload import iter_findings
from wbm.report.templates import format_fact
from wbm.report.validate import allowed_numbers, numbers_in, unknown_numbers


def sample_outcomes() -> list[CheckOutcome]:
    data = bundle(
        orders=orders(1, 28, days_ago=13) + orders(2, 28, days_ago=13),
        stocks=[stock(1, 0), stock(2, 10)],
        feedbacks=[feedback(1, 1, "Брак"), feedback(1, 2, "Плохо")],
    )
    return run_checks(data)


# ── проверка чисел ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("остаток 1 500 шт. и 34,7 %", {Decimal(1500), Decimal("34.7")}),
        ("выручка 2000.50 ₽", {Decimal("2000.5")}),
        ("без чисел", set()),
        ("за 14 дней — 28 заказов", {Decimal(14), Decimal(28)}),
    ],
)
def test_numbers_in(text: str, expected: set[Decimal]) -> None:
    assert numbers_in(text) == expected


def test_rounding_of_source_numbers_is_allowed() -> None:
    allowed = allowed_numbers({"доля_процентов": 34.7, "руб": 2000.0})

    assert unknown_numbers("Около 35 % и 34,7 %, 2 000 ₽", allowed) == []
    assert unknown_numbers("Потери 5 000 ₽ в месяц", allowed) == ["5000"]


def test_fact_formatting() -> None:
    assert (
        format_fact("выручка_в_день_под_угрозой_руб", 2000.5)
        == "выручка в день под угрозой: 2 000,5 ₽"
    )
    assert format_fact("доля_процентов", 34.7) == "доля: 34,7 %"
    assert format_fact("остаток_шт", 0) == "остаток: 0 шт."


# ── сборка отчёта ─────────────────────────────────────────────────────────────


@dataclass
class FakeWriter:
    texts: dict[str, str]
    summary: str = "Главное — пополнить остатки."
    calls: list[dict[str, object]] = field(default_factory=list)

    async def write(self, payload: dict[str, object]) -> LLMReport:
        self.calls.append(payload)
        return LLMReport.model_validate(
            {
                "summary": self.summary,
                "findings": [{"key": k, "text": t} for k, t in self.texts.items()],
            }
        )


class FailingWriter:
    async def write(self, payload: dict[str, object]) -> LLMReport:
        raise ReportWriterError("Claude недоступен (сеть или таймаут)")


async def test_without_claude_uses_templates() -> None:
    outcomes = sample_outcomes()

    report = await generate_report(outcomes, shop_name="Ромашка", period_days=30, writer=None)

    assert report.source == "template"
    assert "Ромашка" in report.summary
    assert len(report.texts) == len(iter_findings(outcomes))
    assert all("Что сделать" in t for t in report.texts.values())


async def test_claude_texts_used_when_numbers_are_honest() -> None:
    outcomes = sample_outcomes()
    keys = [ref.key for ref, _ in iter_findings(outcomes)]
    writer = FakeWriter(
        dict.fromkeys(keys, "Товар заканчивается: заказывают 2 в день. Отгрузите поставку.")
    )

    report = await generate_report(outcomes, shop_name="Ромашка", period_days=30, writer=writer)

    assert report.source == "claude"
    assert report.issues == []
    assert set(report.texts.values()) == {
        "Товар заканчивается: заказывают 2 в день. Отгрузите поставку."
    }
    sent = json.dumps(writer.calls[0], ensure_ascii=False)
    assert "Брак" not in sent  # тексты отзывов в Claude не уходят


async def test_invented_number_replaced_by_template() -> None:
    outcomes = sample_outcomes()
    keys = [ref.key for ref, _ in iter_findings(outcomes)]
    texts = dict.fromkeys(keys, "Всё понятно, отгрузите поставку.")
    texts[keys[0]] = "Вы теряете 150 000 ₽ в месяц."  # такого числа в данных нет
    writer = FakeWriter(texts, summary="Срочно: потери 999 ₽.")

    report = await generate_report(outcomes, shop_name="Ромашка", period_days=30, writer=writer)

    assert report.source == "mixed"
    assert "150 000" not in report.texts[keys[0]]
    assert "Что сделать" in report.texts[keys[0]]
    assert report.texts[keys[1]] == "Всё понятно, отгрузите поставку."
    assert "999" not in report.summary
    assert any("150000" in issue for issue in report.issues)


async def test_missing_text_and_failing_writer() -> None:
    outcomes = sample_outcomes()

    partial = await generate_report(outcomes, shop_name="М", period_days=30, writer=FakeWriter({}))
    failed = await generate_report(outcomes, shop_name="М", period_days=30, writer=FailingWriter())

    assert all("Что сделать" in t for t in partial.texts.values())
    assert failed.source == "template"
    assert failed.issues == ["Claude недоступен (сеть или таймаут)"]


async def test_markdown_report_has_sections() -> None:
    outcomes = sample_outcomes()
    report = await generate_report(outcomes, shop_name="Ромашка", period_days=30, writer=None)

    text = render_markdown(outcomes, report)

    assert text.startswith("# Отчёт об анализе магазина")
    assert "## Критично" in text
    assert "## Не проверено" in text  # без финансов и рекламы часть проверок пропущена


# ── запрос к Claude ───────────────────────────────────────────────────────────


@dataclass
class Block:
    text: str
    type: str = "text"


@dataclass
class Response:
    content: list[Block]
    stop_reason: str = "end_turn"
    model: str = "claude-opus-5-5"


class FakeCreate:
    def __init__(self, response: Response | Exception) -> None:
        self.response = response
        self.kwargs: dict[str, Any] = {}

    async def __call__(self, **kwargs: Any) -> Response:
        self.kwargs = kwargs
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


GOOD = json.dumps({"summary": "Итог", "findings": [{"key": "c0f0", "text": "Текст"}]})


async def test_writer_request_shape() -> None:
    create = FakeCreate(Response([Block(GOOD)]))

    report = await ClaudeReportWriter(create, model="claude-opus-5-5", effort="low").write({"a": 1})

    assert report.findings[0].text == "Текст"
    assert create.kwargs["model"] == "claude-opus-5-5"
    assert create.kwargs["fallbacks"] == "default"
    assert create.kwargs["betas"] == ["server-side-fallback-2026-07-01"]
    assert create.kwargs["output_config"]["effort"] == "low"
    assert create.kwargs["output_config"]["format"]["type"] == "json_schema"
    assert "thinking" not in create.kwargs


async def test_writer_without_fallback_for_other_models() -> None:
    create = FakeCreate(Response([Block(GOOD)]))

    await ClaudeReportWriter(create, model="claude-haiku-5-5").write({})

    assert "fallbacks" not in create.kwargs
    assert "betas" not in create.kwargs


_REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (Response([], stop_reason="refusal"), "отказался"),
        (Response([Block("{")], stop_reason="max_tokens"), "обрезан"),
        (Response([Block("не json")]), "схемой"),
        (Response([Block('{"summary": "x"}')]), "схемой"),
        (Response([]), "нет текста"),
        (anthropic.APIConnectionError(request=_REQUEST), "недоступен"),
    ],
)
async def test_writer_failures(response: Response | Exception, message: str) -> None:
    with pytest.raises(ReportWriterError, match=message):
        await ClaudeReportWriter(FakeCreate(response)).write({})
