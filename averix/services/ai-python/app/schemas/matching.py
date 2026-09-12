"""Shapes for the natural-language layer over the matching engine.

The score itself is computed in Go, deterministically and with reasons. This
service only phrases the reasons for a person — it never produces a number,
and a caller cannot use it to change one.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScoredReason(BaseModel):
    label: str = Field(max_length=160)
    met: bool
    detail: str = Field(default="", max_length=200)


class ExplainRequest(BaseModel):
    project_title: str = Field(max_length=200)
    project_category: str = Field(default="", max_length=80)
    required_skills: list[str] = Field(default_factory=list, max_length=30)
    # The score and reasons as Go computed them. Passed in rather than
    # recomputed so the prose can never disagree with the number shown.
    score: int = Field(ge=0, le=100)
    reasons: list[ScoredReason] = Field(default_factory=list, max_length=20)
    developer_title: str = Field(default="", max_length=120)


class ExplainResponse(BaseModel):
    # Two or three sentences a client can read instead of a bar chart.
    explanation: str = ""
    generated: bool = False
    degraded_reason: str = ""
