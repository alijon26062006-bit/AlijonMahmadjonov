"""Поставщики ИИ: Anthropic и OpenAI. Ключ приносит владелец бота."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Any, Iterable, Protocol

from .spec import BotSpec, normalize, strict_json_schema

log = logging.getLogger(__name__)

ANTHROPIC = "anthropic"
OPENAI = "openai"

MAX_SPEC_TOKENS = 8000
MAX_CHAT_TOKENS = 800


class ProviderError(RuntimeError):
    """Понятная владельцу ошибка обращения к ИИ."""


class Unsupported(ProviderError):
    """Этот поставщик такого не умеет."""


@dataclass(frozen=True)
class ProviderInfo:
    code: str
    title: str
    where: str
    key_prefix: str
    draws: bool


PROVIDERS: dict[str, ProviderInfo] = {
    ANTHROPIC: ProviderInfo(
        code=ANTHROPIC,
        title="Claude (Anthropic)",
        where="platform.claude.com -> API Keys",
        key_prefix="sk-ant-",
        draws=False,
    ),
    OPENAI: ProviderInfo(
        code=OPENAI,
        title="ChatGPT (OpenAI)",
        where="platform.openai.com -> API keys",
        key_prefix="sk-",
        draws=True,
    ),
}


def guess_provider(key: str) -> str | None:
    """Определить поставщика по виду ключа."""
    key = key.strip()
    if key.startswith("sk-ant-"):
        return ANTHROPIC
    if key.startswith("sk-"):
        return OPENAI
    return None


class Provider(Protocol):
    code: str

    async def check(self) -> None: ...

    async def structured(self, system: str, user_text: str) -> BotSpec: ...

    async def chat(self, system: str, messages: list[dict[str, str]]) -> str: ...

    async def draw(self, prompt: str) -> bytes: ...

    async def close(self) -> None: ...


def _json_schema() -> dict[str, Any]:
    return strict_json_schema()


class AnthropicProvider:
    code = ANTHROPIC

    def __init__(self, api_key: str, model: str, chat_model: str) -> None:
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._chat_model = chat_model

    async def close(self) -> None:
        await self._client.close()

    async def check(self) -> None:
        try:
            await self._client.models.list(limit=1)
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(_short(exc)) from exc

    @staticmethod
    def _text(response: Any) -> str:
        for block in response.content:
            if getattr(block, "type", None) == "text":
                return block.text
        raise ProviderError("модель не вернула текст")

    async def structured(self, system: str, user_text: str) -> BotSpec:
        messages = [{"role": "user", "content": user_text}]
        try:
            parse = getattr(self._client.messages, "parse", None)
            if parse is not None:
                response = await parse(
                    model=self._model,
                    max_tokens=MAX_SPEC_TOKENS,
                    system=system,
                    messages=messages,
                    output_format=BotSpec,
                )
                parsed = getattr(response, "parsed_output", None)
                if parsed is not None:
                    return normalize(parsed)
                return normalize(BotSpec.model_validate_json(self._text(response)))

            response = await self._client.messages.create(
                model=self._model,
                max_tokens=MAX_SPEC_TOKENS,
                system=system,
                messages=messages,
                output_config={"format": {"type": "json_schema", "schema": _json_schema()}},
            )
            return normalize(BotSpec.model_validate_json(self._text(response)))
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("Anthropic не собрал структуру бота")
            raise ProviderError(_short(exc)) from exc

    async def chat(self, system: str, messages: list[dict[str, str]]) -> str:
        try:
            response = await self._client.messages.create(
                model=self._chat_model,
                max_tokens=MAX_CHAT_TOKENS,
                system=system,
                messages=messages,
            )
            return self._text(response).strip()
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(_short(exc)) from exc

    async def draw(self, prompt: str) -> bytes:
        raise Unsupported(
            "Claude не рисует картинки. Для генерации фото нужен ключ OpenAI."
        )


class OpenAIProvider:
    code = OPENAI

    def __init__(self, api_key: str, model: str, chat_model: str, image_model: str) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._chat_model = chat_model
        self._image_model = image_model

    async def close(self) -> None:
        await self._client.close()

    async def check(self) -> None:
        try:
            await self._client.models.list()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(_short(exc)) from exc

    async def structured(self, system: str, user_text: str) -> BotSpec:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                max_completion_tokens=MAX_SPEC_TOKENS,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_text},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "bot_spec",
                        "strict": True,
                        "schema": _json_schema(),
                    },
                },
            )
            content = response.choices[0].message.content or ""
            return normalize(BotSpec.model_validate_json(content))
        except Exception as exc:  # noqa: BLE001
            log.exception("OpenAI не собрал структуру бота")
            raise ProviderError(_short(exc)) from exc

    async def chat(self, system: str, messages: list[dict[str, str]]) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self._chat_model,
                max_completion_tokens=MAX_CHAT_TOKENS,
                messages=[{"role": "system", "content": system}, *messages],
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(_short(exc)) from exc

    async def draw(self, prompt: str) -> bytes:
        try:
            result = await self._client.images.generate(
                model=self._image_model, prompt=prompt, n=1, size="1024x1024"
            )
            item = result.data[0]
            if getattr(item, "b64_json", None):
                return base64.b64decode(item.b64_json)
            if getattr(item, "url", None):
                return await self._download(item.url)
            raise ProviderError("сервис не вернул картинку")
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(_short(exc)) from exc

    @staticmethod
    async def _download(url: str) -> bytes:
        import asyncio
        import urllib.request

        def fetch() -> bytes:
            with urllib.request.urlopen(url, timeout=60) as response:
                return response.read()

        return await asyncio.to_thread(fetch)


def _short(exc: Exception) -> str:
    """Из длинной технической ошибки сделать строку, понятную владельцу."""
    text = str(exc)
    lowered = text.lower()
    if "authentication" in lowered or "invalid_api_key" in lowered or "401" in lowered:
        return "ключ не принят — проверьте, что он действующий и скопирован целиком"
    if "insufficient_quota" in lowered or "credit balance" in lowered or "billing" in lowered:
        return "на счету поставщика закончились деньги"
    if "rate limit" in lowered or "429" in lowered:
        return "слишком много запросов подряд, попробуйте через минуту"
    if "model" in lowered and "not" in lowered and "found" in lowered:
        return "такой модели нет у поставщика — поменяйте её в настройках .env"
    return text[:300]


def build(code: str, api_key: str, models: dict[str, str]) -> Provider:
    """Создать поставщика по коду."""
    if code == ANTHROPIC:
        return AnthropicProvider(
            api_key=api_key,
            model=models.get("anthropic_model", "claude-opus-5"),
            chat_model=models.get("anthropic_chat_model", "claude-sonnet-5"),
        )
    if code == OPENAI:
        return OpenAIProvider(
            api_key=api_key,
            model=models.get("openai_model", "gpt-4o"),
            chat_model=models.get("openai_chat_model", "gpt-4o-mini"),
            image_model=models.get("openai_image_model", "dall-e-3"),
        )
    raise ProviderError(f"неизвестный поставщик: {code}")
