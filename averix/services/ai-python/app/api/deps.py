"""Request dependencies: authentication and the service singletons."""

from __future__ import annotations

import hmac
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.ai.client import ModelClient
from app.config import Settings, get_settings
from app.services.analysis import AnalysisService
from app.services.assistant import AssistantService
from app.services.explain import ExplainService


@lru_cache
def get_model_client() -> ModelClient:
    return ModelClient(get_settings())


@lru_cache
def get_analysis_service() -> AnalysisService:
    return AnalysisService(get_settings(), get_model_client())


@lru_cache
def get_assistant_service() -> AssistantService:
    return AssistantService(get_settings(), get_model_client())


@lru_cache
def get_explain_service() -> ExplainService:
    return ExplainService(get_model_client())


async def require_service_token(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Authenticates the calling service.

    This service is not public: only the Go API talks to it, and the token is
    what enforces that if the network ever fails to. The comparison is
    constant-time so the token cannot be recovered by timing.

    In development the token may be unset, and the service is then open — which
    is why config.validate_for_runtime refuses to start in production without
    one.
    """
    if not settings.service_token:
        return

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="a service token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    presented = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(presented, settings.service_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="the service token is not valid",
        )


ServiceAuth = Annotated[None, Depends(require_service_token)]
