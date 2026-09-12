"""The client-facing project assistant.

A client who says "I need a Telegram bot for my clothing store" should not be
asked to choose a framework. This service asks what their customers will do,
then turns the answers into a brief a developer can quote against.

It proposes and never publishes: the Go API stores the result as a draft, and
the client edits and publishes it. It also never sets a budget, because only
the client knows what they can spend.

Without a model configured, the deterministic fallback still works: the
category is guessed from keywords and a standard question set is returned.
That is a genuinely smaller product, and it says so — it does not pretend a
model wrote it.
"""

from __future__ import annotations

from app.ai.client import ModelClient, ModelUnavailable
from app.ai.prompts import (
    PROJECT_ASSISTANT_SYSTEM,
    PROJECT_DRAFT_SYSTEM,
    assistant_questions_prompt,
    project_draft_prompt,
)
from app.config import Settings
from app.logging import get_logger
from app.schemas.assistant import (
    DraftFeature,
    DraftMilestone,
    DraftRequest,
    DraftResponse,
    Question,
    StartRequest,
    StartResponse,
)
from app.taxonomy import CATEGORY_SLUGS, SKILL_SLUGS

log = get_logger(__name__)

# Keyword hints for the deterministic category guess. Ordered most specific
# first, because "telegram mini app" must not resolve to a plain bot and
# "online store" must not swallow a store's Telegram bot.
_CATEGORY_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("telegram-mini-apps", ("mini app", "mini-app", "miniapp", "telegram web app")),
    ("telegram-bots", ("telegram bot", "telegram-bot", "bot for telegram", "telegram")),
    ("mobile-applications", ("mobile app", "ios app", "android app", "iphone", "flutter", "react native")),
    ("ai-automation", ("chatbot", "ai ", "gpt", "llm", "machine learning", "automation", "openai")),
    ("ecommerce", ("online store", "shop", "e-commerce", "ecommerce", "storefront", "catalogue", "catalog")),
    ("saas", ("saas", "subscription", "multi-tenant", "multi tenant")),
    ("api-development", ("api", "rest api", "integration endpoint", "webhook")),
    ("integrations", ("integrate", "integration", "sync with", "connect to")),
    ("devops", ("ci/cd", "pipeline", "deploy", "kubernetes", "docker")),
    ("infrastructure", ("server", "hosting", "infrastructure", "database migration")),
    ("ui-ux-digital", ("design", "redesign", "ui ", "ux ", "figma", "mockup")),
    ("frontend-development", ("landing page", "website front", "frontend", "front-end")),
    ("backend-development", ("backend", "back-end", "server-side", "admin panel")),
    ("web-applications", ("web app", "dashboard", "portal", "internal tool")),
)

# The standard question set, used when no model is available and as the
# grounding for what the model is asked to produce. Every one of these changes
# the work; none of them asks a non-technical client about architecture.
_FALLBACK_QUESTIONS: tuple[Question, ...] = (
    Question(
        key="who_uses_it",
        question="Who will be using this?",
        options=["My customers", "My staff", "Both"],
        help_text="This changes how much of the work is customer-facing.",
    ),
    Question(
        key="payments",
        question="Do people need to pay inside it?",
        options=["Yes", "No", "Not at first"],
        help_text="Taking payment adds real work and usually a provider account.",
    ),
    Question(
        key="admin_area",
        question="Do you need an area for your staff to manage things?",
        options=["Yes", "No", "Not sure"],
        help_text="For example adding products, or seeing and updating orders.",
    ),
    Question(
        key="existing_system",
        question="Does this need to connect to anything you already use?",
        options=["Yes", "No", "Not sure"],
        help_text="An accounting system, a warehouse, a CRM, a delivery service.",
    ),
    Question(
        key="languages",
        question="Which languages does it need to work in?",
        options=["One language", "Two languages", "More than two"],
        optional=True,
    ),
    Question(
        key="timeline",
        question="When do you need it?",
        options=["As soon as possible", "Within a month", "Within three months", "No fixed date"],
    ),
)


class AssistantService:
    def __init__(self, settings: Settings, model: ModelClient) -> None:
        self._settings = settings
        self._model = model

    async def start(self, request: StartRequest) -> StartResponse:
        guessed, confidence = guess_category(request.description)

        if not self._model.configured:
            return StartResponse(
                suggested_category=guessed,
                category_confidence=confidence,
                questions=list(_FALLBACK_QUESTIONS),
                understanding="",
                generated=False,
                degraded_reason="no model is configured on this environment",
            )

        try:
            payload, _ = await self._model.complete_json(
                system=PROJECT_ASSISTANT_SYSTEM,
                prompt=assistant_questions_prompt(
                    description=request.description, categories=sorted(CATEGORY_SLUGS)
                ),
                max_tokens=1200,
            )
        except ModelUnavailable as exc:
            return StartResponse(
                suggested_category=guessed,
                category_confidence=confidence,
                questions=list(_FALLBACK_QUESTIONS),
                generated=False,
                degraded_reason=str(exc),
            )

        category = str(payload.get("category", "")).strip()
        if category not in CATEGORY_SLUGS:
            # The model named something outside the taxonomy; the keyword
            # guess is a better answer than an unusable slug.
            category = guessed

        questions = _parse_questions(payload.get("questions"))
        if not questions:
            questions = list(_FALLBACK_QUESTIONS)

        raw_confidence = payload.get("confidence", confidence)
        try:
            parsed_confidence = min(max(float(raw_confidence), 0.0), 1.0)
        except (TypeError, ValueError):
            parsed_confidence = confidence

        return StartResponse(
            suggested_category=category,
            category_confidence=parsed_confidence,
            questions=questions,
            understanding=str(payload.get("understanding", "")).strip()[:300],
            generated=True,
        )

    async def draft(self, request: DraftRequest) -> DraftResponse:
        guessed, _ = guess_category(request.description)

        if not self._model.configured:
            # A skeleton the client fills in, clearly labelled as not drafted.
            return DraftResponse(
                title=_title_from(request.description),
                description=request.description.strip(),
                category_slug=guessed,
                generated=False,
                degraded_reason="no model is configured on this environment",
                open_questions=[
                    "Describe what your customers should be able to do, step by step.",
                    "Is there anything this must connect to?",
                    "What does success look like when it is finished?",
                ],
            )

        try:
            payload, model = await self._model.complete_json(
                system=PROJECT_DRAFT_SYSTEM,
                prompt=project_draft_prompt(
                    description=request.description,
                    answers=dict(request.answers),
                    categories=sorted(CATEGORY_SLUGS),
                    skills=sorted(SKILL_SLUGS),
                ),
                max_tokens=2500,
            )
        except ModelUnavailable as exc:
            return DraftResponse(
                title=_title_from(request.description),
                description=request.description.strip(),
                category_slug=guessed,
                generated=False,
                degraded_reason=str(exc),
            )

        category = str(payload.get("category_slug", "")).strip()
        if category not in CATEGORY_SLUGS:
            category = guessed

        # Only technologies from the taxonomy survive. A model that invents
        # "microservices" as a technology would produce a project nobody can
        # be matched against.
        skills = [
            slug
            for slug in _string_list(payload.get("suggested_skills"))
            if slug in SKILL_SLUGS
        ][:12]

        return DraftResponse(
            title=str(payload.get("title", "")).strip()[:140] or _title_from(request.description),
            summary=str(payload.get("summary", "")).strip()[:300],
            description=str(payload.get("description", "")).strip() or request.description.strip(),
            category_slug=category,
            suggested_skills=skills,
            features=_parse_features(payload.get("features")),
            milestones=_parse_milestones(payload.get("milestones")),
            estimated_scale=_strip_money(str(payload.get("estimated_scale", "")).strip()[:120]),
            open_questions=_string_list(payload.get("open_questions"))[:8],
            generated=True,
            model=model,
        )


def guess_category(description: str) -> tuple[str, float]:
    """Guesses a category from keywords.

    Deliberately simple and deliberately honest about it: the returned
    confidence is low, and the client always sees and can change the category.
    """
    lowered = " " + " ".join(description.lower().split()) + " "
    for slug, hints in _CATEGORY_HINTS:
        for hint in hints:
            if hint in lowered:
                # Low by construction: a keyword match is a hint, not a
                # classification, and overstating it would make the client
                # trust a guess they should be checking.
                return slug, 0.45
    return "", 0.0


def _parse_questions(raw: object) -> list[Question]:
    if not isinstance(raw, list):
        return []
    out: list[Question] = []
    for item in raw[:6]:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", "")).strip()[:60]
        question = str(item.get("question", "")).strip()[:300]
        if not key or not question:
            continue
        out.append(
            Question(
                key=key,
                question=question,
                options=[str(o).strip()[:80] for o in _string_list(item.get("options"))][:6],
                optional=bool(item.get("optional", False)),
                help_text=str(item.get("help_text", "")).strip()[:300],
            )
        )
    return out


def _parse_features(raw: object) -> list[DraftFeature]:
    if not isinstance(raw, list):
        return []
    out: list[DraftFeature] = []
    for item in raw[:30]:
        if isinstance(item, str):
            title = item.strip()[:160]
            if title:
                out.append(DraftFeature(title=title))
            continue
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()[:160]
        if not title:
            continue
        out.append(
            DraftFeature(
                title=title,
                detail=str(item.get("detail", "")).strip()[:600],
                required=bool(item.get("required", True)),
            )
        )
    return out


def _parse_milestones(raw: object) -> list[DraftMilestone]:
    if not isinstance(raw, list):
        return []

    parsed: list[DraftMilestone] = []
    for item in raw[:12]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()[:160]
        if not title:
            continue
        try:
            share = min(max(float(item.get("share", 0)), 0.0), 1.0)
        except (TypeError, ValueError):
            share = 0.0
        try:
            days = min(max(int(item.get("days", 0)), 0), 365)
        except (TypeError, ValueError):
            days = 0
        parsed.append(
            DraftMilestone(
                title=title,
                detail=str(item.get("detail", "")).strip()[:600],
                share=share,
                days=days,
            )
        )

    # The shares must add to 1, or the client sees a plan that does not account
    # for their whole budget. Normalising is better than rejecting a draft that
    # is otherwise fine.
    total = sum(m.share for m in parsed)
    if parsed and total > 0 and abs(total - 1.0) > 0.01:
        for milestone in parsed:
            milestone.share = round(milestone.share / total, 4)
    elif parsed and total <= 0:
        equal = round(1.0 / len(parsed), 4)
        for milestone in parsed:
            milestone.share = equal
    return parsed


def _string_list(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _title_from(description: str) -> str:
    """A serviceable title from the client's own words, for the fallback."""
    cleaned = " ".join(description.split())
    if not cleaned:
        return "New project"
    for terminator in (". ", "! ", "? ", "\n"):
        if terminator in cleaned:
            cleaned = cleaned.split(terminator, 1)[0]
            break
    cleaned = cleaned.rstrip(".!?")
    if len(cleaned) > 120:
        cut = cleaned[:120]
        cleaned = cut[: cut.rfind(" ")] if " " in cut else cut
    return cleaned[:1].upper() + cleaned[1:]


def _strip_money(text: str) -> str:
    """Removes a figure from the scale estimate.

    The assistant is told never to price work, and this is the guard for when
    it does anyway: a number the client reads as a quote would anchor every
    proposal they then receive.
    """
    if any(symbol in text for symbol in ("$", "€", "£", "USD", "EUR")):
        return ""
    return text
