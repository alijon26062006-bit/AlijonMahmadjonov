"""Claude превращает готовые результаты проверок в понятный текст. Цифры он не считает."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import anthropic
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Вы помогаете продавцу Wildberries понять отчёт об анализе его магазина.
Вам передают готовые результаты проверок в JSON: для каждой проблемы — важность,
заголовок, факты (цифры из данных магазина), причину, рекомендацию, товары и иногда оговорку.

Напишите на русском:
- для каждой проблемы (по её key) текст из 2–4 предложений: что случилось, почему это
  важно для продаж или денег, что сделать в первую очередь;
- краткий итог отчёта из 2–4 предложений: главные проблемы и с чего начать.

Правила:
- Используйте только числа из входных данных. Ничего не вычисляйте и не придумывайте:
  ни сумм, ни процентов, ни сроков, ни дат. Если числа нет в данных — пишите без числа.
- Не добавляйте фактов и причин, которых нет в данных.
- Если у проблемы есть «оговорка», обязательно упомяните её — она о возможном сбое данных.
- Пишите просто и по делу, обращайтесь на «вы», без канцелярита и без markdown.
- Ответ — только JSON по заданной схеме."""

OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"key": {"type": "string"}, "text": {"type": "string"}},
                "required": ["key", "text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "findings"],
    "additionalProperties": False,
}

# Модели, для которых включаем серверный запасной вариант при отказе классификатора.
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class ReportWriterError(Exception):
    """Claude не дал пригодный текст — отчёт соберётся по шаблонам."""


class _FindingText(BaseModel):
    key: str
    text: str


class LLMReport(BaseModel):
    summary: str
    findings: list[_FindingText]


CreateMessage = Callable[..., Awaitable[Any]]


class ClaudeReportWriter:
    def __init__(
        self,
        create: CreateMessage,
        *,
        model: str = "claude-opus-5-5",
        effort: str = "low",
        max_tokens: int = 16000,
    ) -> None:
        self._create = create
        self._model = model
        self._effort = effort
        self._max_tokens = max_tokens

    @classmethod
    def from_api_key(
        cls, api_key: str, *, model: str, effort: str, timeout: float
    ) -> ClaudeReportWriter:
        client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout)
        return cls(client.beta.messages.create, model=model, effort=effort)

    async def write(self, payload: dict[str, object]) -> LLMReport:
        request: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "system": SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=1)}
            ],
            "output_config": {
                "effort": self._effort,
                "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
            },
        }
        if self._model in _FALLBACK_MODELS:
            request["betas"] = [_FALLBACK_BETA]
            request["fallbacks"] = "default"

        try:
            response = await self._create(**request)
        except anthropic.RateLimitError as exc:
            raise ReportWriterError("Claude: превышен лимит запросов") from exc
        except anthropic.APIStatusError as exc:
            raise ReportWriterError(f"Claude ответил ошибкой HTTP {exc.status_code}") from exc
        except anthropic.APIConnectionError as exc:
            raise ReportWriterError("Claude недоступен (сеть или таймаут)") from exc

        stop_reason = getattr(response, "stop_reason", None)
        if stop_reason == "refusal":
            raise ReportWriterError("Claude отказался писать текст")
        if stop_reason == "max_tokens":
            raise ReportWriterError("Текст Claude обрезан по длине")
        text = next(
            (block.text for block in response.content if getattr(block, "type", None) == "text"),
            None,
        )
        if text is None:
            raise ReportWriterError("В ответе Claude нет текста")
        try:
            report = LLMReport.model_validate_json(text)
        except ValidationError as exc:
            raise ReportWriterError("Ответ Claude не совпадает со схемой") from exc
        logger.info(
            "Claude написал текст отчёта: модель %s, проблем %d",
            getattr(response, "model", self._model),
            len(report.findings),
        )
        return report
