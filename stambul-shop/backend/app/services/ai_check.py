"""Сверка обработанной фотографии с оригиналом.

Генеративная ретушь может незаметно изменить товар: убрать пуговицу,
подтереть логотип, укоротить изделие. Заметить это в потоке из двадцати
карточек человек не в состоянии, поэтому сверка идёт отдельным проходом
и по списку, а не «на глаз».

Правило простое: не сошлось — карточка не публикуется сама, а помечается
«нужна проверка». Ошибиться в сторону осторожности здесь дёшево, в другую
сторону — это возвраты и споры с покупателем.
"""
import base64
import json

import httpx

API_URL = "https://api.openai.com/v1/chat/completions"
TIMEOUT = 90

SYSTEM = """Ты приёмщик товарной фотографии. Тебе дают два изображения
одной и той же вещи: первое — исходный снимок, второе — обработанный для
каталога.

Твоя работа — найти расхождения в самом товаре. Разница в фоне,
освещении, положении вещи в кадре, наличии вешалки и в мелких складках
от хранения — это нормально, так и задумано, о ней сообщать не нужно.

Сообщать нужно об изменениях товара:
- другой цвет или оттенок ткани;
- другое количество пуговиц, молний, карманов;
- изменившийся воротник, вырез, длина изделия или рукава;
- пропавшие или добавленные надписи, логотипы, принты, вышивка, кружево,
  стразы, жемчуг;
- изменившийся узор или рисунок ткани;
- появившиеся детали, которых не было на оригинале.

severity: "none" — товар тот же; "minor" — отличие есть, но мелкое и
спорное; "major" — товар изменился, публиковать нельзя.

Ответ — только JSON, без пояснений."""

SCHEMA_HINT = """Верни объект:
{"same_product": bool, "severity": "none"|"minor"|"major",
 "differences": [строки на русском], "note": строка}"""


class CheckError(Exception):
    pass


async def compare(original: bytes, processed: bytes, *, api_key: str,
                  model: str) -> dict:
    if not api_key:
        raise CheckError("Не задан ключ OpenAI")
    if not original or not processed:
        raise CheckError("Нечего сравнивать")

    def data_url(raw: bytes) -> str:
        return "data:image/png;base64," + base64.b64encode(raw).decode()

    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": [
                {"type": "text", "text": "Первое — оригинал."},
                {"type": "image_url",
                 "image_url": {"url": data_url(original), "detail": "high"}},
                {"type": "text", "text": "Второе — обработанное. "
                                         + SCHEMA_HINT},
                {"type": "image_url",
                 "image_url": {"url": data_url(processed), "detail": "high"}},
            ]},
        ],
        "max_tokens": 500,
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                API_URL, json=payload,
                headers={"Authorization": f"Bearer {api_key}"})
    except httpx.HTTPError as error:
        raise CheckError(f"Не дозвонился до OpenAI: {error}") from None

    if response.status_code >= 400:
        raise CheckError(f"OpenAI отказал: {response.status_code}")

    try:
        content = response.json()["choices"][0]["message"]["content"]
        verdict = json.loads(content)
    except (KeyError, IndexError, json.JSONDecodeError):
        raise CheckError("Не разобрал ответ проверки") from None

    return clean(verdict)


def clean(verdict: dict) -> dict:
    severity = str(verdict.get("severity", "")).lower()
    if severity not in ("none", "minor", "major"):
        # Непонятный ответ считаем поводом для проверки человеком: молчаливо
        # пропускать сомнительное — ровно то, ради чего эта сверка и нужна.
        severity = "minor"

    raw = verdict.get("differences")
    differences = [" ".join(str(x).split())[:160] for x in raw][:8] \
        if isinstance(raw, list) else []

    same = bool(verdict.get("same_product", severity == "none"))
    if severity == "major":
        same = False

    return {
        "same_product": same,
        "severity": severity,
        "differences": differences,
        "note": " ".join(str(verdict.get("note", "")).split())[:300],
    }


def status_of(verdict: dict | None) -> str:
    """Что делать с карточкой: ok — можно показывать, review — руками."""
    if verdict is None:
        return "skipped"
    return "ok" if verdict["severity"] == "none" else "review"
