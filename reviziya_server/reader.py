"""Чтение цены с фото ценника через Claude."""

from __future__ import annotations

import logging
import re

import anthropic

log = logging.getLogger("reviziya.reader")

SYSTEM = "\n".join([
    "Ты читаешь цену с ценника или бирки товара в магазине одежды. На фото кадр с камеры телефона.",
    "Цена: число на наклейке от этикет-пистолета, число рядом со словом «Цена», "
    "или число, написанное ручкой на бирке или листке бумаги.",
    "Не цена: год на логотипе бренда (1913, SINCE 1985, EST. 1990), размер, состав ткани в процентах, "
    "штрихкод, артикул, дата, телефон.",
    "Рукописные буквы «о» внутри числа считай нулями.",
    "Ответь одной строкой без других слов:",
    "- только число цифрами без пробелов, например 3000",
    "- число и знак вопроса, если сомневаешься хотя бы в одной цифре, например 3000?",
    "- минус (-), если ценника нет или цену нельзя прочитать",
])

MAX_PRICE = 100_000_000


class ReaderError(Exception):
    """Claude не ответил. code: auth, rate, network, rejected, other."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(detail or code)
        self.code = code


def parse_answer(text: str) -> tuple[int, bool]:
    """Ответ Claude -> (цена, сомневается ли). Цена 0 значит «ценник не прочитан»."""
    t = (text or "").strip()
    if not t or t[0] in "-−":
        return 0, False
    match = re.search(r"\d[\d  ]*", t)
    if not match:
        return 0, False
    price = int(re.sub(r"\D", "", match.group()))
    if not 0 < price < MAX_PRICE:
        return 0, False
    return price, "?" in t


def thinking_off(model: str) -> dict:
    # Размышление выключено ради скорости; у разных моделей это пишется по-разному.
    return {"type": "disabled"} if model == "claude-haiku-5-5" else {"type": "between_tools"}


class PriceReader:
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key, max_retries=1, timeout=20.0)
        self.model = model

    async def warm_up(self) -> None:
        """Открывает соединение с Claude заранее, чтобы первый скан не ждал лишнюю секунду."""
        try:
            await self.client.models.retrieve(self.model)
        except Exception as exc:  # не страшно: первый скан просто будет чуть дольше
            log.info("разогрев не удался: %s", exc)

    async def read(self, image_b64: str) -> tuple[int, bool]:
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=32,
                thinking=thinking_off(self.model),
                output_config={"effort": "low"},
                system=SYSTEM,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64}},
                        {"type": "text", "text": "Какая цена?"},
                    ],
                }],
            )
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            raise ReaderError("auth", str(exc)) from exc
        except anthropic.RateLimitError as exc:
            raise ReaderError("rate", str(exc)) from exc
        except anthropic.BadRequestError as exc:
            log.error("Claude отклонил запрос: %s", exc)
            raise ReaderError("rejected", str(exc)) from exc
        except anthropic.APIConnectionError as exc:
            raise ReaderError("network", str(exc)) from exc
        except anthropic.APIStatusError as exc:
            raise ReaderError("other", str(exc)) from exc

        if response.stop_reason == "refusal":
            return 0, False
        text = next((block.text for block in response.content if block.type == "text"), "")
        return parse_answer(text)
