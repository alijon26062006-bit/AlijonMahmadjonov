"""The HTTP surface.

Every route is authenticated with the service token and every response
declares whether a model produced it, so the Go API can label generated
content and show a configuration state rather than silently degrading.
"""

from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import (
    ServiceAuth,
    get_analysis_service,
    get_assistant_service,
    get_explain_service,
    get_model_client,
)
from app.ai.client import ModelClient
from app.config import Settings, get_settings
from app.logging import get_logger
from app.schemas.assistant import DraftRequest, DraftResponse, StartRequest, StartResponse
from app.schemas.github import AnalyseRequest, AnalyseResponse
from app.schemas.matching import ExplainRequest, ExplainResponse
from app.services.analysis import AnalysisService
from app.services.assistant import AssistantService
from app.services.explain import ExplainService

log = get_logger(__name__)

router = APIRouter()
_started = time.monotonic()


@router.get("/health", tags=["health"])
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, object]:
    """Liveness. Touches no dependency, so a model outage cannot make an
    orchestrator kill a healthy container."""
    return {
        "status": "ok",
        "service": "averix-ai",
        "version": "1.0.0",
        "uptime_sec": int(time.monotonic() - _started),
        "environment": settings.app_env,
    }


@router.get("/ready", tags=["health"])
async def ready(
    settings: Annotated[Settings, Depends(get_settings)],
    model: Annotated[ModelClient, Depends(get_model_client)],
) -> dict[str, object]:
    """Readiness.

    An unconfigured model is reported as degraded rather than not-ready: the
    deterministic analysis, the fallback question set and the plain
    explanation all still work, so the service is useful and should keep
    receiving traffic.
    """
    model_ready = model.configured
    return {
        "status": "ready" if model_ready else "degraded",
        "components": {
            "model": {
                "status": "ok" if model_ready else "not_configured",
                "required": False,
                "model": model.model if model_ready else "",
            }
        },
        "deterministic_analysis": "ok",
        "environment": settings.app_env,
    }


@router.post("/v1/github/analyse", response_model=AnalyseResponse, tags=["github"])
async def analyse_github(
    request: AnalyseRequest,
    _: ServiceAuth,
    service: Annotated[AnalysisService, Depends(get_analysis_service)],
) -> AnalyseResponse:
    """Analyses a developer's repositories.

    The deterministic findings always come back. The prose summary is present
    only when a model produced it, and `summary_generated` says which.
    """
    log.info(
        "github analysis requested",
        analysis_id=request.analysis_id,
        repositories=len(request.repositories),
    )
    response = await service.analyse(request)
    log.info(
        "github analysis finished",
        analysis_id=request.analysis_id,
        status=response.status,
        technologies=len(response.technologies),
        summary_generated=response.summary_generated,
    )
    return response


@router.post("/v1/assistant/start", response_model=StartResponse, tags=["assistant"])
async def assistant_start(
    request: StartRequest,
    _: ServiceAuth,
    service: Annotated[AssistantService, Depends(get_assistant_service)],
) -> StartResponse:
    """Turns a client's description into a category guess and a few questions."""
    return await service.start(request)


@router.post("/v1/assistant/draft", response_model=DraftResponse, tags=["assistant"])
async def assistant_draft(
    request: DraftRequest,
    _: ServiceAuth,
    service: Annotated[AssistantService, Depends(get_assistant_service)],
) -> DraftResponse:
    """Drafts a brief from the description and the answers.

    The result is a draft. Nothing here publishes anything: the client reviews
    and publishes it themselves, through the Go API.
    """
    return await service.draft(request)


@router.post("/v1/matching/explain", response_model=ExplainResponse, tags=["matching"])
async def explain_match(
    request: ExplainRequest,
    _: ServiceAuth,
    service: Annotated[ExplainService, Depends(get_explain_service)],
) -> ExplainResponse:
    """Phrases an already-computed match score.

    The score arrives computed and is never recalculated here, so the prose
    and the number a client sees cannot disagree.
    """
    return await service.explain(request)
