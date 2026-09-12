"""The model client.

Every method here can fail to produce anything, and says so. There is no
fallback that invents text: an endpoint whose model is unavailable returns
`generated=False` with a reason, and the interface shows a configuration
state rather than a plausible-looking sentence nobody wrote.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.logging import get_logger

log = get_logger(__name__)


class ModelUnavailable(Exception):
    """Raised when no model can be reached.

    Callers catch this and degrade; they never substitute a canned answer.
    """


@dataclass(slots=True)
class Completion:
    text: str
    model: str


class ModelClient:
    """A thin wrapper over the Anthropic SDK.

    Thin on purpose: the value in this service is the prompts and the
    structured contracts around them, not an abstraction over the SDK.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Any = None

    @property
    def configured(self) -> bool:
        return self._settings.model_configured

    @property
    def model(self) -> str:
        return self._settings.model

    def _ensure_client(self) -> Any:
        if not self.configured:
            raise ModelUnavailable("no model API key is configured")
        if self._client is None:
            # Imported lazily so the service starts, serves health checks and
            # runs its deterministic endpoints without the SDK installed.
            try:
                from anthropic import AsyncAnthropic
            except ImportError as exc:  # pragma: no cover - deployment issue
                raise ModelUnavailable("the anthropic package is not installed") from exc
            self._client = AsyncAnthropic(
                api_key=self._settings.anthropic_api_key,
                timeout=self._settings.model_timeout_seconds,
                max_retries=2,
            )
        return self._client

    async def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float = 0.2,
    ) -> Completion:
        """Asks for prose."""
        client = self._ensure_client()
        try:
            message = await client.messages.create(
                model=self._settings.model,
                max_tokens=max_tokens or self._settings.max_output_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            # The SDK raises a family of errors (overload, rate limit,
            # timeout); none of them should surface to a user as a 500.
            log.warning("model request failed", error=str(exc), model=self._settings.model)
            raise ModelUnavailable(f"the model could not be reached: {type(exc).__name__}") from exc

        text = "".join(
            block.text for block in getattr(message, "content", []) if getattr(block, "type", "") == "text"
        ).strip()
        if not text:
            raise ModelUnavailable("the model returned an empty response")
        return Completion(text=text, model=self._settings.model)

    async def complete_json(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float = 0.1,
    ) -> tuple[dict[str, Any], str]:
        """Asks for a JSON object and parses it.

        A model asked for JSON sometimes wraps it in prose or a code fence.
        Rather than tightening the prompt and hoping, the response is
        recovered from the first balanced object in the text — and if there is
        none, that is a failure, not something to paper over.
        """
        completion = await self.complete(
            system=system + "\n\nRespond with a single JSON object and nothing else.",
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        payload = _extract_json_object(completion.text)
        if payload is None:
            log.warning("model returned unparseable JSON", preview=completion.text[:200])
            raise ModelUnavailable("the model did not return valid JSON")
        return payload, completion.model


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Finds the first balanced JSON object in a string."""
    stripped = text.strip()
    # The common case: the whole response is the object.
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(stripped)):
        char = stripped[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(stripped[start : index + 1])
                except json.JSONDecodeError:
                    return None
                return parsed if isinstance(parsed, dict) else None
    return None
