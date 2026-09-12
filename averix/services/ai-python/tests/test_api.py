"""API behaviour, with the emphasis on honest degradation.

The suite runs with no model configured. That is the case most likely to be
wrong in a real deployment and the one where the product's integrity is at
stake: an endpoint that invents a technical profile when it cannot reach a
model would put words in a developer's mouth that a client will hold them to.
"""

from __future__ import annotations

import json
from typing import Any

from app.schemas.github import AnalyseRequest, ManifestFile, RepositoryInput
from app.schemas.matching import ExplainRequest, ScoredReason


def test_health_touches_nothing(client: Any) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["service"] == "averix-ai"


def test_ready_reports_degraded_without_a_model(client: Any) -> None:
    """A missing model is degraded, not unready.

    The deterministic analysis, the fallback questions and the plain
    explanation all still work, so the service should keep receiving traffic.
    """
    response = client.get("/ready")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "degraded"
    assert body["components"]["model"]["status"] == "not_configured"
    assert body["components"]["model"]["required"] is False
    assert body["deterministic_analysis"] == "ok"


def test_health_endpoints_leak_no_configuration(client: Any) -> None:
    for path in ("/health", "/ready"):
        raw = client.get(path).text
        for secret in ("api_key", "sk-", "AI_API_KEY", "service_token", "AI_SERVICE_TOKEN"):
            assert secret not in raw, f"{path} leaks {secret}"


# ── GitHub analysis ─────────────────────────────────────────────────────────


def telegram_bot_repository() -> dict[str, Any]:
    return {
        "repository_id": "11111111-1111-1111-1111-111111111111",
        "name": "store-bot",
        "full_name": "ali/store-bot",
        "description": "Telegram bot for a clothing store: catalogue, cart and orders.",
        "homepage": "https://bot.example.com",
        "topics": ["telegram", "python"],
        "primary_language": "Python",
        "languages": {"Python": 82_000, "Dockerfile": 900},
        "stars": 14,
        "size_kb": 1200,
        "readme": "# Store bot\n\nA Telegram bot that lets customers browse a catalogue and place orders.",
        "manifests": [
            {
                "name": "requirements.txt",
                "content": "aiogram==3.13.1\nasyncpg~=0.29\nredis>=5.0\npydantic==2.9.0\n",
            },
            {"name": "Dockerfile", "content": "FROM python:3.12-slim\nCOPY . /app\n"},
        ],
    }


def test_analysis_returns_deterministic_findings_without_a_model(client: Any) -> None:
    response = client.post(
        "/v1/github/analyse",
        json={
            "analysis_id": "22222222-2222-2222-2222-222222222222",
            "github_login": "ali",
            "repositories": [telegram_bot_repository()],
            "declared_skills": ["python", "telegram-api", "go"],
            "declared_specialisation": "Telegram Developer",
        },
    )
    assert response.status_code == 200
    body = response.json()

    # The findings that become evidence are all present.
    assert body["repositories_analysed"] == 1
    slugs = {t["skill_slug"] for t in body["technologies"]}
    for expected in ("python", "aiogram", "postgresql", "redis", "docker"):
        assert expected in slugs, f"{expected} was not detected (got {sorted(slugs)})"

    languages = {entry["language"]: entry["share"] for entry in body["language_shares"]}
    assert "Python" in languages
    assert abs(sum(languages.values()) - 1.0) < 0.001

    # And the summary is honestly absent rather than fabricated.
    assert body["summary"] == ""
    assert body["summary_generated"] is False
    assert body["status"] == "partial"
    assert "no model" in body["degraded_reason"].lower()


def test_analysis_reports_corroboration_and_gaps(client: Any) -> None:
    """Declared technologies are checked against the code, not replaced by it."""
    response = client.post(
        "/v1/github/analyse",
        json={
            "analysis_id": "33333333-3333-3333-3333-333333333333",
            "github_login": "ali",
            "repositories": [telegram_bot_repository()],
            # Go is claimed but appears nowhere in the code.
            "declared_skills": ["python", "aiogram", "go"],
            "want_summary": False,
        },
    )
    body = response.json()

    assert "python" in body["corroborated_skills"]
    assert "go" in body["unsupported_skills"], (
        "a declared technology with no evidence should be reported as unsupported"
    )
    # Technologies found in the code that were not claimed are offered, never
    # added: the analysis does not edit anyone's profile.
    assert "redis" in body["suggested_skills"] or "postgresql" in body["suggested_skills"]
    for slug in body["suggested_skills"]:
        assert slug not in body["corroborated_skills"]


def test_forks_contribute_technologies_but_not_language_share(client: Any) -> None:
    """A fork's code was not written by the developer.

    Its dependencies still say something about what they have worked with, but
    counting its bytes towards their language share would credit them with
    someone else's code.
    """
    own = telegram_bot_repository()
    fork = telegram_bot_repository() | {
        "repository_id": "44444444-4444-4444-4444-444444444444",
        "full_name": "ali/forked-django-thing",
        "is_fork": True,
        "primary_language": "Ruby",
        "languages": {"Ruby": 5_000_000},
        "manifests": [{"name": "Gemfile", "content": 'gem "rails"\n'}],
    }

    body = client.post(
        "/v1/github/analyse",
        json={
            "analysis_id": "55555555-5555-5555-5555-555555555555",
            "github_login": "ali",
            "repositories": [own, fork],
            "want_summary": False,
        },
    ).json()

    languages = {entry["language"] for entry in body["language_shares"]}
    assert "Ruby" not in languages, "a fork's bytes must not count towards language share"
    assert "Python" in languages

    slugs = {t["skill_slug"] for t in body["technologies"]}
    assert "ruby" in slugs, "a fork's dependencies are still evidence of exposure"

    # And a fork is never offered as portfolio work.
    by_id = {f["repository_id"]: f for f in body["findings"]}
    assert by_id[fork["repository_id"]]["portfolio_candidate"] is False
    assert "fork" in by_id[fork["repository_id"]]["candidate_reason"]


def test_analysis_generates_a_summary_when_a_model_is_available(
    settings: Any, stub_model: Any
) -> None:
    from app.services.analysis import AnalysisService

    model = stub_model(
        text="Public repositories show a focus on Python backend work with Telegram "
        "integrations, backed by PostgreSQL and deployed with Docker.",
        payload={"purpose": "A Telegram bot for a clothing store.", "category": "telegram-bots"},
    )
    service = AnalysisService(settings, model)

    request = AnalyseRequest(
        analysis_id="66666666-6666-6666-6666-666666666666",
        github_login="ali",
        repositories=[RepositoryInput(**telegram_bot_repository())],
        declared_specialisation="Telegram Developer",
    )
    import asyncio

    response = asyncio.run(service.analyse(request))

    assert response.status == "succeeded"
    assert response.summary_generated is True
    assert response.summary_model == "stub-model"
    assert "Python" in response.summary
    # The generated purpose is attached to the repository it describes.
    assert response.findings[0].inferred_purpose
    assert response.findings[0].suggested_category == "telegram-bots"


def test_a_model_failure_leaves_the_deterministic_findings_intact(
    settings: Any, stub_model: Any
) -> None:
    import asyncio

    from app.services.analysis import AnalysisService

    service = AnalysisService(settings, stub_model(fail=True))
    response = asyncio.run(
        service.analyse(
            AnalyseRequest(
                analysis_id="77777777-7777-7777-7777-777777777777",
                github_login="ali",
                repositories=[RepositoryInput(**telegram_bot_repository())],
            )
        )
    )

    assert response.status == "partial"
    assert response.summary == ""
    assert response.summary_generated is False
    assert response.degraded_reason
    # The findings that matter are unaffected.
    assert {t.skill_slug for t in response.technologies} >= {"python", "aiogram"}


def test_a_category_outside_the_taxonomy_is_dropped(settings: Any, stub_model: Any) -> None:
    """A model that invents a category must not have it stored.

    A slug nobody can search for is worse than none at all.
    """
    import asyncio

    from app.services.analysis import AnalysisService

    model = stub_model(
        text="A summary.",
        payload={"purpose": "Something.", "category": "quantum-blockchain-synergy"},
    )
    response = asyncio.run(
        AnalysisService(settings, model).analyse(
            AnalyseRequest(
                analysis_id="88888888-8888-8888-8888-888888888888",
                github_login="ali",
                repositories=[RepositoryInput(**telegram_bot_repository())],
            )
        )
    )
    assert response.findings[0].suggested_category == ""


def test_analysis_bounds_the_work_it_accepts(client: Any) -> None:
    """One developer with hundreds of repositories cannot monopolise the service."""
    repositories = []
    for index in range(120):
        repo = telegram_bot_repository()
        repo["repository_id"] = f"{index:08d}-0000-0000-0000-000000000000"
        repo["full_name"] = f"ali/repo-{index}"
        repositories.append(repo)

    body = client.post(
        "/v1/github/analyse",
        json={
            "analysis_id": "99999999-9999-9999-9999-999999999999",
            "github_login": "ali",
            "repositories": repositories,
            "want_summary": False,
        },
    ).json()

    assert body["repositories_seen"] == 120
    assert body["repositories_analysed"] <= 60, "the analysis must cap the work it does"


def test_malformed_analysis_request_is_rejected_without_echoing_input(client: Any) -> None:
    response = client.post("/v1/github/analyse", json={"github_login": "ali"})
    assert response.status_code == 422

    body = response.json()
    assert body["error"]["code"] == "validation_failed"
    assert "analysis_id" in body["error"]["fields"]
    # Pydantic's default body echoes the offending input, which here can be a
    # README or a client's description.
    assert "input" not in json.dumps(body)


# ── Assistant ───────────────────────────────────────────────────────────────


def test_assistant_start_without_a_model_still_asks_useful_questions(client: Any) -> None:
    body = client.post(
        "/v1/assistant/start",
        json={"description": "I need a Telegram bot for my clothing store so customers can order."},
    ).json()

    assert body["suggested_category"] == "telegram-bots"
    assert body["generated"] is False
    assert body["degraded_reason"]
    assert len(body["questions"]) >= 4

    # The questions must be answerable by someone who has never written code.
    joined = " ".join(q["question"].lower() for q in body["questions"])
    for jargon in ("framework", "database", "architecture", "api", "stack", "deploy"):
        assert jargon not in joined, f"a client should not be asked about {jargon}"
    for question in body["questions"]:
        assert question["key"] and question["question"]


def test_category_guessing_is_specific_and_honest(client: Any) -> None:
    cases = {
        "I need a Telegram mini app for booking tables": "telegram-mini-apps",
        "A telegram bot to answer customer questions": "telegram-bots",
        "An iOS app for our delivery drivers": "mobile-applications",
        "An online store selling handmade rugs": "ecommerce",
        "We need a REST API our partners can integrate with": "api-development",
        "A dashboard for our staff to see orders": "web-applications",
        "Redesign the look of our product": "ui-ux-digital",
    }
    for description, expected in cases.items():
        body = client.post("/v1/assistant/start", json={"description": description}).json()
        assert body["suggested_category"] == expected, (
            f"{description!r} guessed {body['suggested_category']!r}, expected {expected!r}"
        )
        # A keyword match is a hint, and the confidence must say so.
        assert 0 < body["category_confidence"] <= 0.5

    # Nothing recognisable produces no guess rather than a wrong one.
    body = client.post(
        "/v1/assistant/start", json={"description": "Something vague about our business."}
    ).json()
    assert body["suggested_category"] == ""
    assert body["category_confidence"] == 0.0


def test_assistant_draft_never_invents_a_price(settings: Any, stub_model: Any) -> None:
    """The assistant must not price work.

    A figure the client reads as a quote would anchor every proposal they then
    receive, and only they know what they can spend.
    """
    import asyncio

    from app.schemas.assistant import DraftRequest
    from app.services.assistant import AssistantService

    model = stub_model(
        payload={
            "title": "Telegram bot for a clothing store",
            "summary": "Catalogue, cart and orders inside Telegram.",
            "description": "We run a clothing store.\n\nWe want customers to order in Telegram.",
            "category_slug": "telegram-bots",
            "suggested_skills": ["python", "telegram-api", "postgresql", "not-a-real-technology"],
            "features": [
                {"title": "Product catalogue", "required": True},
                {"title": "Cart", "detail": "Add and remove items", "required": True},
            ],
            "milestones": [
                {"title": "Catalogue", "share": 0.4, "days": 5},
                {"title": "Cart and orders", "share": 0.4, "days": 5},
                {"title": "Admin panel", "share": 0.4, "days": 4},
            ],
            # A model ignoring its instructions and quoting a figure.
            "estimated_scale": "about two weeks, roughly $800",
            "open_questions": ["Do you have a payment provider?"],
        }
    )
    response = asyncio.run(
        AssistantService(settings, model).draft(
            DraftRequest(description="A Telegram bot for my clothing store.", answers={"payments": "Yes"})
        )
    )

    assert response.generated is True
    assert response.category_slug == "telegram-bots"
    # An invented technology is dropped.
    assert "not-a-real-technology" not in response.suggested_skills
    assert set(response.suggested_skills) == {"python", "telegram-api", "postgresql"}
    # The shares are normalised to 1 even though the model's added to 1.2.
    assert abs(sum(m.share for m in response.milestones) - 1.0) < 0.01
    # And the figure is stripped.
    assert "$" not in response.estimated_scale
    assert response.estimated_scale == ""


def test_assistant_draft_without_a_model_returns_a_labelled_skeleton(client: Any) -> None:
    body = client.post(
        "/v1/assistant/draft",
        json={
            "description": "I need a Telegram bot for my clothing store. Customers should browse and order.",
            "answers": {"payments": "Yes"},
        },
    ).json()

    assert body["generated"] is False
    assert body["degraded_reason"]
    assert body["category_slug"] == "telegram-bots"
    # A usable title from the client's own words, not a fabricated brief.
    assert body["title"].startswith("I need a Telegram bot")
    assert body["open_questions"], "the client should be told what to fill in"
    assert body["features"] == []
    assert body["milestones"] == []


# ── Match explanation ───────────────────────────────────────────────────────


def test_explanation_never_contradicts_the_score(client: Any) -> None:
    body = client.post(
        "/v1/matching/explain",
        json={
            "project_title": "Telegram bot for an online store",
            "project_category": "telegram-bots",
            "required_skills": ["python", "telegram-api", "postgresql"],
            "score": 94,
            "developer_title": "Backend Developer",
            "reasons": [
                {"label": "Python", "met": True, "detail": "verified"},
                {"label": "Telegram API", "met": True, "detail": "verified"},
                {"label": "PostgreSQL", "met": True, "detail": "strong"},
                {"label": "Available for work", "met": True, "detail": ""},
                {"label": "Redis", "met": False, "detail": ""},
            ],
        },
    ).json()

    assert body["generated"] is False
    assert body["explanation"]
    # The plain fallback states both sides.
    assert "Python" in body["explanation"]
    assert "Redis" in body["explanation"]
    # It must not invent a second percentage.
    assert "%" not in body["explanation"]


def test_deterministic_explanation_is_even_handed() -> None:
    from app.services.explain import deterministic_explanation

    all_met = deterministic_explanation(
        ExplainRequest(
            project_title="A project",
            score=96,
            reasons=[ScoredReason(label="Go", met=True), ScoredReason(label="Docker", met=True)],
        )
    )
    assert "Go" in all_met and "Docker" in all_met
    assert "Does not cover" not in all_met

    with_gap = deterministic_explanation(
        ExplainRequest(
            project_title="A project",
            score=60,
            reasons=[ScoredReason(label="Go", met=True), ScoredReason(label="Kubernetes", met=False)],
        )
    )
    assert "Does not cover Kubernetes" in with_gap

    empty = deterministic_explanation(ExplainRequest(project_title="A project", score=0))
    assert empty, "an explanation must always say something"


# ── Service authentication ──────────────────────────────────────────────────


def test_service_token_is_required_when_configured(monkeypatch: Any) -> None:
    """This service is not public.

    Only the Go API talks to it, and the token is what enforces that if the
    network ever fails to.
    """
    from fastapi.testclient import TestClient

    from app.api import deps
    from app.config import Settings, get_settings

    token = "a-service-token-long-enough-to-be-real-0001"
    get_settings.cache_clear()
    monkeypatch.setenv("AI_SERVICE_TOKEN", token)
    # The dependency caches are keyed on the settings singleton.
    deps.get_model_client.cache_clear()
    deps.get_analysis_service.cache_clear()
    deps.get_assistant_service.cache_clear()
    deps.get_explain_service.cache_clear()

    try:
        from app.main import app

        with TestClient(app) as client:
            payload = {"description": "I need a Telegram bot for my clothing store."}

            assert client.post("/v1/assistant/start", json=payload).status_code == 401
            assert (
                client.post(
                    "/v1/assistant/start",
                    json=payload,
                    headers={"Authorization": "Bearer the-wrong-token"},
                ).status_code
                == 401
            )
            assert (
                client.post(
                    "/v1/assistant/start", json=payload, headers={"Authorization": token}
                ).status_code
                == 401
            ), "a token without the Bearer scheme must be refused"
            assert (
                client.post(
                    "/v1/assistant/start",
                    json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                ).status_code
                == 200
            )
            # Health checks stay open so an orchestrator can probe them.
            assert client.get("/health").status_code == 200
            assert client.get("/ready").status_code == 200
    finally:
        monkeypatch.delenv("AI_SERVICE_TOKEN", raising=False)
        get_settings.cache_clear()
        deps.get_model_client.cache_clear()
        deps.get_analysis_service.cache_clear()
        deps.get_assistant_service.cache_clear()
        deps.get_explain_service.cache_clear()


def test_production_refuses_to_start_without_a_service_token() -> None:
    from app.config import Settings

    problems = Settings(app_env="production", service_token="").validate_for_runtime()
    assert any("AI_SERVICE_TOKEN" in problem for problem in problems)

    problems = Settings(app_env="production", service_token="short").validate_for_runtime()
    assert any("at least 32" in problem for problem in problems)

    ok = Settings(app_env="production", service_token="x" * 40).validate_for_runtime()
    assert ok == []
