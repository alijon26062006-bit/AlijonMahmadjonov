"""Test fixtures.

The suite runs with no model configured, which is the important case to get
right: the deterministic layer must stand on its own and every generative
endpoint must degrade honestly rather than inventing content. The generative
path is exercised separately with a stubbed client.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("AI_SERVICE_TOKEN", "")
os.environ.setdefault("AI_API_KEY", "")
os.environ.setdefault("LOG_LEVEL", "error")


@pytest.fixture
def client() -> Iterator[Any]:
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def settings() -> Any:
    from app.config import Settings

    return Settings(app_env="test", service_token="", anthropic_api_key="")


class StubModel:
    """A model client that returns whatever a test hands it.

    Used to exercise the generative path, including the cases that matter
    most: a model that fails, and a model that returns something outside the
    taxonomy.
    """

    def __init__(
        self,
        *,
        configured: bool = True,
        text: str = "",
        payload: dict[str, Any] | None = None,
        fail: bool = False,
    ) -> None:
        self._configured = configured
        self._text = text
        self._payload = payload or {}
        self._fail = fail
        self.calls = 0

    @property
    def configured(self) -> bool:
        return self._configured

    @property
    def model(self) -> str:
        return "stub-model"

    async def complete(self, **_: Any) -> Any:
        from app.ai.client import Completion, ModelUnavailable

        self.calls += 1
        if self._fail:
            raise ModelUnavailable("stub failure")
        return Completion(text=self._text, model="stub-model")

    async def complete_json(self, **_: Any) -> tuple[dict[str, Any], str]:
        from app.ai.client import ModelUnavailable

        self.calls += 1
        if self._fail:
            raise ModelUnavailable("stub failure")
        return self._payload, "stub-model"


@pytest.fixture
def stub_model() -> type[StubModel]:
    return StubModel
