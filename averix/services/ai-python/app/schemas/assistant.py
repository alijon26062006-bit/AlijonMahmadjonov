"""Shapes for the client-facing project assistant.

The assistant's job is to turn "I need a Telegram bot for my clothing store"
into a brief a developer can quote against, without asking the client to
choose an architecture. It proposes; the client always reviews and publishes.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AssistantTurn(BaseModel):
    role: Literal["client", "assistant"]
    content: str = Field(max_length=4_000)


class Question(BaseModel):
    """One question for the client, in plain language."""

    key: str = Field(max_length=60)
    question: str = Field(max_length=300)
    # A closed set of answers where there is one, so the client taps rather
    # than types on a phone.
    options: list[str] = Field(default_factory=list, max_length=8)
    # Whether the brief can be drafted without an answer.
    optional: bool = False
    help_text: str = Field(default="", max_length=300)


class StartRequest(BaseModel):
    """The client's opening description, in their own words."""

    description: str = Field(min_length=8, max_length=4_000)
    locale: str = Field(default="en", max_length=12)


class StartResponse(BaseModel):
    # The category the description most resembles, as a taxonomy slug.
    suggested_category: str = ""
    category_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    # What still needs to be known, ordered by how much each answer changes
    # the brief.
    questions: list[Question] = Field(default_factory=list)
    # A one-line restatement, so the client can see they were understood
    # before answering anything.
    understanding: str = ""
    generated: bool = False
    degraded_reason: str = ""


class DraftRequest(BaseModel):
    description: str = Field(min_length=8, max_length=4_000)
    # The answers to the questions, keyed by question key.
    answers: dict[str, str | bool | list[str]] = Field(default_factory=dict)
    transcript: list[AssistantTurn] = Field(default_factory=list, max_length=40)
    locale: str = Field(default="en", max_length=12)


class DraftFeature(BaseModel):
    title: str = Field(max_length=160)
    detail: str = Field(default="", max_length=600)
    required: bool = True


class DraftMilestone(BaseModel):
    title: str = Field(max_length=160)
    detail: str = Field(default="", max_length=600)
    # A share of the total, not an amount: the assistant does not price work.
    share: float = Field(ge=0.0, le=1.0)
    days: int = Field(default=0, ge=0, le=365)


class DraftResponse(BaseModel):
    """A brief for the client to review.

    Nothing here is published: the Go API stores it as a draft and the client
    edits and publishes it themselves. The assistant never sets a budget,
    because only the client knows what they can spend.
    """

    title: str = ""
    summary: str = ""
    description: str = ""
    category_slug: str = ""
    # Technologies the work implies, for the client to accept or change.
    suggested_skills: list[str] = Field(default_factory=list)
    features: list[DraftFeature] = Field(default_factory=list)
    milestones: list[DraftMilestone] = Field(default_factory=list)
    # A rough scale, in plain language rather than a figure: "a few weeks".
    estimated_scale: str = ""
    # Anything the assistant could not determine and the client should decide.
    open_questions: list[str] = Field(default_factory=list)
    generated: bool = False
    model: str = ""
    degraded_reason: str = ""
