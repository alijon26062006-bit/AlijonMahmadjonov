"""The AVERIX analysis service.

Go owns every business action and every write. This service reads what it is
given, analyses it, and returns structured findings. It holds no database
credentials, no OAuth tokens and no session state — so a compromise here
cannot change a contract, release a payment or read a private message.

The boundary is also why the GitHub OAuth token stays in Go: this service
receives already-fetched repository material rather than the credential to
fetch it with.
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.deps import get_model_client
from app.api.routes import router
from app.config import get_settings
from app.logging import configure, get_logger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure(level=settings.log_level, json_output=settings.app_env != "development")

    problems = settings.validate_for_runtime()
    if problems:
        for problem in problems:
            log.error("invalid configuration", problem=problem)
        # Failing to start is the correct response to a misconfigured
        # deployment: a service running without its service token in
        # production is worse than one that is down.
        sys.exit(1)

    model = get_model_client()
    log.info(
        "averix-ai starting",
        environment=settings.app_env,
        port=settings.port,
        model_configured=model.configured,
        model=model.model if model.configured else "",
        service_token_set=bool(settings.service_token),
    )
    if not model.configured:
        log.warning(
            "no model configured: analysis returns deterministic findings only, "
            "and generated content is reported as unavailable rather than invented"
        )
    yield
    log.info("averix-ai stopped")


app = FastAPI(
    title="AVERIX analysis service",
    version="1.0.0",
    description=(
        "Repository analysis, technical profiles, the client project assistant "
        "and match explanations for the AVERIX marketplace."
    ),
    lifespan=lifespan,
    # The schema is useful internally and is not exposed publicly: nginx does
    # not route to this service from the internet.
    docs_url="/docs",
    openapi_url="/openapi.json",
)
app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Reports a malformed request in the shape the Go API expects.

    Pydantic's default body includes the input that failed, which for this
    service can be a README or a client's description — not something to echo
    back into another service's logs.
    """
    fields: dict[str, str] = {}
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ()) if part != "body")
        fields[location or "body"] = str(error.get("msg", "is not valid"))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": {"code": "validation_failed", "fields": fields}},
    )


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    """Turns an unexpected failure into a safe response.

    The cause goes to the log; the caller gets a code and nothing about the
    internals.
    """
    log.error(
        "unhandled error",
        path=request.url.path,
        error=str(exc),
        error_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": {"code": "internal_error", "message": "The analysis service failed."}},
    )
