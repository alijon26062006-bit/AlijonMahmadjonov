"""Проверка чека ИИ до админа: не чек / нет реквизитов / реквизиты не наши — отказ сразу.

Нет ключа OpenAI, PDF или ИИ не ответил — чек уходит админу, как обычно.
"""
from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any

import httpx

log = logging.getLogger(__name__)

NOT_RECEIPT = ("Ваша фотография не является чеком. Пришлите скриншот чека о переводе. / "
               "Сурати шумо чек нест. Скриншоти чеки интиқолро фиристед.")
NO_DETAILS = ("Вы отправили недействительный чек: в нём нет реквизитов получателя. / "
              "Чеки фиристодаи шумо беэътибор аст: дар он реквизитҳои гиранда нест.")
WRONG_DETAILS = ("В чеке не найдены наши реквизиты. Проверьте свой перевод и пришлите чек заново. / "
                 "Дар чек реквизитҳои мо ёфт нашуд. Интиқоли худро санҷед ва чекро аз нав фиристед.")
MASK = "*•·xX#"
PROMPT = (
    "Это скриншот банковского чека (Таджикистан: Алиф, Душанбе Сити, Эсхата и др.). Верни ТОЛЬКО JSON: "
    '{"is_receipt": true/false, "amount": число, "currency": "TJS|USD|…", "recipient": "получатель точно как в чеке: '
    'номер карты или телефона со звёздочками-масками и имя", "recipient_ok": "yes|no|unknown"}. '
    "Получатель — КУДА ушли деньги («Получатель», «Кому», «Қабулкунанда», «Гиранда», «Recipient»), "
    "не путай с отправителем. recipient_ok — совпадает ли получатель с НАШИМИ реквизитами ниже. Не придумывай.\n"
    "НАШИ реквизиты: "
)


def read(api_key: str, model: str, data: bytes, ext: str, our_details: str,
         transport: httpx.BaseTransport | None = None) -> dict[str, Any] | None:
    mime = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext)
    if not api_key or not mime:
        return None
    body = {"model": model, "temperature": 0, "max_tokens": 300, "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": PROMPT + re.sub(r"\s+", " ", our_details)[:1500]},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode()}",
                                                    "detail": "high"}}]}]}
    try:
        with httpx.Client(timeout=25, transport=transport) as c:
            r = c.post("https://api.openai.com/v1/chat/completions", json=body,
                       headers={"Authorization": f"Bearer {api_key}"})
        if r.status_code != 200:
            log.warning("чек: OpenAI %s", r.status_code)
            return None
        raw = json.loads(r.json()["choices"][0]["message"]["content"])
    except Exception:  # noqa: BLE001 — проверка чека не должна ломать пополнение
        log.exception("чек: не прочитан")
        return None
    return {"is_receipt": raw.get("is_receipt") is not False, "recipient": str(raw.get("recipient") or "").strip()[:200],
            "recipient_ok": str(raw.get("recipient_ok") or "unknown").lower(), "amount": raw.get("amount"),
            "currency": str(raw.get("currency") or "")[:8]}


def _numbers(details: str) -> list[str]:
    return [d for d in (re.sub(r"\D", "", m) for m in re.findall(r"\+?\d[\d \-]{7,}\d", details or "")) if len(d) >= 9]


def _chunks(recipient: str) -> list[str]:
    return [c.strip() for c in re.findall(r"\+?[\d" + re.escape(MASK) + r"][\d" + re.escape(MASK) + r" \-.]*", recipient or "")
            if sum(ch.isdigit() for ch in c) >= 4]


def _strip992(num: str) -> str:
    return num[3:] if num.startswith("992") and len(num) == 12 else num


def fits(chunk: str, num: str) -> bool:
    """Подходит ли номер из чека (возможно с маской) к нашему номеру."""
    num = _strip992(num)
    marks = [i for i, ch in enumerate(chunk) if ch in MASK]
    if marks:
        head = re.sub(r"\D", "", chunk[:marks[0]])
        head = head[3:] if head.startswith("992") and len(num) <= 9 else head
        tail = re.sub(r"\D", "", chunk[marks[-1] + 1:])
        if len(head) + len(tail) < 4 or len(tail) < 2:
            return False
        return num.startswith(head) and num.endswith(tail)
    digits = _strip992(re.sub(r"\D", "", chunk))
    if len(digits) == 4:
        return num.endswith(digits)
    return len(digits) >= 9 and digits[-9:] == num[-9:]


def refuse(d: dict[str, Any] | None, our_details: str) -> str | None:
    """Текст отказа клиенту или None — чек идёт админу."""
    if not d:
        return None
    if d.get("is_receipt") is False:
        return NOT_RECEIPT
    ours = _numbers(our_details)
    if not ours or d.get("recipient_ok") == "yes":
        return None
    rec = d.get("recipient") or ""
    if not rec:
        return NO_DETAILS
    chunks = _chunks(rec)
    if chunks and not any(fits(c, n) for c in chunks for n in ours):
        return WRONG_DETAILS
    return None
