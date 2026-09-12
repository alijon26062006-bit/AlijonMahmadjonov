"""Natural-language explanation of a match score.

The number and its reasons are computed in Go, deterministically. This service
only phrases them. It cannot produce or change a score, which is why a client
can trust that the sentence and the percentage agree.
"""

from __future__ import annotations

from app.ai.client import ModelClient, ModelUnavailable
from app.ai.prompts import MATCH_EXPLANATION_SYSTEM, match_explanation_prompt
from app.schemas.matching import ExplainRequest, ExplainResponse


class ExplainService:
    def __init__(self, model: ModelClient) -> None:
        self._model = model

    async def explain(self, request: ExplainRequest) -> ExplainResponse:
        if not self._model.configured:
            return ExplainResponse(
                explanation=deterministic_explanation(request),
                generated=False,
                degraded_reason="no model is configured on this environment",
            )

        try:
            completion = await self._model.complete(
                system=MATCH_EXPLANATION_SYSTEM,
                prompt=match_explanation_prompt(
                    project_title=request.project_title,
                    developer_title=request.developer_title,
                    score=request.score,
                    reasons=[(r.label, r.met, r.detail) for r in request.reasons],
                ),
                max_tokens=300,
            )
        except ModelUnavailable as exc:
            return ExplainResponse(
                explanation=deterministic_explanation(request),
                generated=False,
                degraded_reason=str(exc),
            )

        return ExplainResponse(explanation=completion.text.strip(), generated=True)


def deterministic_explanation(request: ExplainRequest) -> str:
    """Assembles the reasons into a sentence without a model.

    Plainer than generated prose, and always available. The reasons are the
    same ones the score was built from, so this is never wrong — only drier.
    """
    met = [r.label for r in request.reasons if r.met]
    unmet = [r.label for r in request.reasons if not r.met]

    parts: list[str] = []
    if met:
        parts.append("Matches on " + _join(met[:4]) + ".")
    if unmet:
        parts.append("Does not cover " + _join(unmet[:2]) + ".")
    if not parts:
        return "No match details were recorded for this pairing."
    return " ".join(parts)


def _join(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f" and {items[-1]}"
