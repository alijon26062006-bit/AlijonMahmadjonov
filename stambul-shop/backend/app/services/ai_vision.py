"""Разбор фотографии товара языковой моделью.

Модель здесь только предлагает: название, раздел, цвет, материал, сезон и
текст описания. Ничего из этого не публикуется само — владелец видит
черновик и подтверждает. Так и должно быть: модель уверенно ошибается, а
покупатель потом получает не ту вещь.

Отдельное правило: не выдумывать. Бренд, состав ткани и страну по снимку
надёжно не определить, поэтому в сомнительных случаях поле остаётся
пустым, а не заполняется правдоподобной чепухой.
"""
import base64
import json

import httpx

from app.catalog.schemas import COLORS, all_categories

API_URL = "https://api.openai.com/v1/chat/completions"
TIMEOUT = 90


class VisionError(Exception):
    """Ошибка разбора, которую показываем владельцу словами."""


SYSTEM = """Ты помощник продавца интернет-магазина. По фотографии товара
готовишь черновик карточки на русском языке.

Строгие правила:
- Пиши только то, что видно на фотографии.
- Бренд указывай, только если логотип или надпись читаются целиком.
  Иначе оставь пустую строку.
- Состав ткани и страну производства по фотографии определить нельзя:
  оставляй пустыми, если их не видно на бирке.
- Не придумывай размеры, цену, количество и артикул.
- Название — короткое и человеческое, как в магазине: «Мужские кроссовки
  на шнуровке», а не «Товар №1» и не рекламный лозунг.
- Описание — два-четыре предложения о том, что видно: тип вещи, крой,
  цвет, из чего похоже сделано, к чему подойдёт. Без восклицаний, без
  «спешите купить», без выдуманных характеристик.
- category выбирай строго из предложенного списка. Если ничего не
  подходит, верни пустую строку и предложи название нового раздела в
  поле category_suggest.

Ответ — только JSON, без пояснений."""

SCHEMA_HINT = """Верни объект с полями:
{"title": str, "category": str, "category_suggest": str, "brand": str,
 "color": str, "material": str, "season": str, "style": str,
 "description": str, "uncertain": [str]}
uncertain — список названий полей, в которых ты не уверен."""


def _categories_block() -> str:
    return "\n".join(f"- {c.slug}: {c.title}" for c in all_categories())


async def analyze(image: bytes, api_key: str, model: str) -> dict:
    """Возвращает черновик карточки. Бросает VisionError, если не вышло."""
    if not api_key:
        raise VisionError("Не задан ключ OpenAI")
    if not image:
        raise VisionError("Нет фотографии для разбора")

    payload = {
        "model": model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": [
                {"type": "text", "text":
                    f"Разделы магазина:\n{_categories_block()}\n\n"
                    f"Допустимые цвета: {', '.join(COLORS)}\n\n{SCHEMA_HINT}"},
                {"type": "image_url", "image_url": {
                    "url": "data:image/jpeg;base64,"
                           + base64.b64encode(image).decode(),
                    "detail": "low"}},
            ]},
        ],
        "max_tokens": 700,
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                API_URL, json=payload,
                headers={"Authorization": f"Bearer {api_key}"})
    except httpx.HTTPError as error:
        raise VisionError(f"Не дозвонился до OpenAI: {error}") from None

    if response.status_code == 401:
        raise VisionError("Ключ OpenAI не принят")
    if response.status_code == 429:
        raise VisionError("Слишком часто либо кончился лимит OpenAI")
    if response.status_code >= 400:
        detail = response.json().get("error", {}).get("message", "")
        raise VisionError(f"OpenAI ответил ошибкой: {detail[:200]}")

    try:
        content = response.json()["choices"][0]["message"]["content"]
        draft = json.loads(content)
    except (KeyError, IndexError, json.JSONDecodeError):
        raise VisionError("Не разобрал ответ модели") from None

    return clean(draft)


def clean(draft: dict) -> dict:
    """Оставляет только то, чему можно верить, и обрезает по длине."""
    def text(key: str, limit: int) -> str:
        value = draft.get(key)
        return " ".join(str(value).split())[:limit] if isinstance(value, str) else ""

    category = text("category", 40)
    if category and not any(c.slug == category for c in all_categories()):
        category = ""

    colour = text("color", 40)
    if colour and colour not in COLORS:
        # цвет пишем только из своего списка: иначе фильтр каталога
        # засорится синонимами вроде «чёрный матовый»
        colour = next((c for c in COLORS if c.lower() in colour.lower()), "")

    uncertain = draft.get("uncertain")
    uncertain = [str(x)[:40] for x in uncertain][:8] if isinstance(uncertain, list) else []

    return {
        "title": text("title", 160),
        "category": category,
        "category_suggest": text("category_suggest", 80),
        "brand": text("brand", 80),
        "color": colour,
        "material": text("material", 120),
        "season": text("season", 40),
        "style": text("style", 40),
        "description": text("description", 1200),
        "uncertain": uncertain,
    }
