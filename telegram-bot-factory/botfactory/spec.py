"""Структура бота: то, что генерирует ИИ и исполняет движок."""

from __future__ import annotations

import html
import re
from typing import Any, List, Literal

from pydantic import BaseModel, Field

MAX_COMMANDS = 12
MAX_TRIGGERS = 24
MAX_MENU_BUTTONS = 8
MAX_INLINE_BUTTONS = 6
MAX_TEXT = 3000
MAX_BUTTON_TEXT = 40

_COMMAND_RE = re.compile(r"[^a-z0-9_]")


class Button(BaseModel):
    """Кнопка под сообщением."""

    text: str = Field(description="Надпись на кнопке")
    action: Literal["message", "url"] = Field(
        description="message — прислать текст, url — открыть ссылку"
    )
    value: str = Field(description="Текст ответа или ссылка, начинающаяся с https://")


class Command(BaseModel):
    """Команда бота, например /menu."""

    command: str = Field(description="Название команды без слеша, латиницей")
    description: str = Field(description="Короткое описание для меню команд Telegram")
    reply_text: str = Field(description="Что бот отвечает на эту команду")
    buttons: List[Button] = Field(description="Кнопки под ответом, можно пустой список")


class Trigger(BaseModel):
    """Ответ на ключевые слова в обычном сообщении."""

    keywords: List[str] = Field(description="Слова или фразы, на которые срабатывает ответ")
    reply_text: str = Field(description="Что отвечает бот")


class AISettings(BaseModel):
    """Режим свободного общения через Claude."""

    enabled: bool = Field(description="Отвечать ли своими словами, когда заготовки не подошли")
    persona: str = Field(description="Характер бота: дружелюбный, деловой, с юмором, эксперт")
    system_prompt: str = Field(
        description="Инструкция для ИИ: кто он, что знает о бизнесе, что можно и нельзя говорить"
    )


class BotSpec(BaseModel):
    """Полное описание поведения бота."""

    name: str = Field(description="Название бота для владельца")
    description: str = Field(description="Одно предложение: чем занимается бот")
    welcome_text: str = Field(description="Первое сообщение по команде /start")
    menu_buttons: List[str] = Field(
        description="Надписи кнопок нижней клавиатуры, каждая должна быть обработана"
    )
    commands: List[Command] = Field(description="Команды бота, без /start")
    triggers: List[Trigger] = Field(description="Ответы на ключевые слова")
    ai: AISettings
    fallback_text: str = Field(description="Ответ, когда ничего не подошло и ИИ выключен")


def _clip(text: str, limit: int = MAX_TEXT) -> str:
    text = (text or "").strip()
    return text[:limit]


def _clean_command(raw: str) -> str:
    name = _COMMAND_RE.sub("", (raw or "").strip().lstrip("/").lower())
    return name[:32]


def normalize(spec: BotSpec) -> BotSpec:
    """Привести сгенерированную структуру к тому, что Telegram реально принимает."""
    data: dict[str, Any] = spec.model_dump()

    data["name"] = _clip(data["name"], 64) or "Бот"
    data["description"] = _clip(data["description"], 200)
    data["welcome_text"] = _clip(data["welcome_text"]) or "Здравствуйте!"
    data["fallback_text"] = _clip(data["fallback_text"]) or "Не совсем понял вопрос."

    menu: list[str] = []
    for label in data.get("menu_buttons") or []:
        label = _clip(str(label), MAX_BUTTON_TEXT)
        if label and label not in menu:
            menu.append(label)
    data["menu_buttons"] = menu[:MAX_MENU_BUTTONS]

    commands: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in data.get("commands") or []:
        name = _clean_command(item.get("command", ""))
        if not name or name in seen or name == "start":
            continue
        seen.add(name)

        buttons: list[dict[str, Any]] = []
        for btn in item.get("buttons") or []:
            text = _clip(btn.get("text", ""), MAX_BUTTON_TEXT)
            value = _clip(btn.get("value", ""))
            action = btn.get("action") if btn.get("action") in ("message", "url") else "message"
            if action == "url" and not value.startswith(("https://", "http://", "tg://")):
                action = "message"
            if not text or not value:
                continue
            buttons.append({"text": text, "action": action, "value": value})

        commands.append(
            {
                "command": name,
                "description": _clip(item.get("description", ""), 200) or name,
                "reply_text": _clip(item.get("reply_text", "")) or "…",
                "buttons": buttons[:MAX_INLINE_BUTTONS],
            }
        )
    data["commands"] = commands[:MAX_COMMANDS]

    triggers: list[dict[str, Any]] = []
    for item in data.get("triggers") or []:
        keywords = []
        for word in item.get("keywords") or []:
            word = _clip(str(word), 80).lower()
            if word:
                keywords.append(word)
        reply = _clip(item.get("reply_text", ""))
        if keywords and reply:
            triggers.append({"keywords": keywords, "reply_text": reply})
    data["triggers"] = triggers[:MAX_TRIGGERS]

    ai = data.get("ai") or {}
    data["ai"] = {
        "enabled": bool(ai.get("enabled", True)),
        "persona": _clip(ai.get("persona", ""), 100) or "дружелюбный",
        "system_prompt": _clip(ai.get("system_prompt", ""), 4000) or data["description"],
    }

    return BotSpec.model_validate(data)


def lint(spec: BotSpec) -> list[str]:
    """Найти места, где бот промолчит. Не ошибки, а предупреждения для владельца."""
    problems: list[str] = []
    if not spec.ai.enabled:
        handled = {word.lower() for t in spec.triggers for word in t.keywords}
        handled |= {c.description.lower() for c in spec.commands}
        for label in spec.menu_buttons:
            if label.lower() not in handled:
                problems.append(f"кнопка «{label}» ни к чему не привязана")
    if not spec.commands and not spec.triggers and not spec.ai.enabled:
        problems.append("бот умеет только здороваться — нет ни команд, ни ответов, ни ИИ")
    return problems


def summary(spec: BotSpec) -> str:
    """Короткое описание бота для предпросмотра в чате фабрики. Формат HTML."""

    def esc(value: str) -> str:
        return html.escape(value)

    lines = [f"<b>{esc(spec.name)}</b>", esc(spec.description), ""]
    lines.append("<b>Приветствие</b>")
    lines.append(esc(spec.welcome_text[:400]))
    lines.append("")

    if spec.menu_buttons:
        lines.append("<b>Кнопки меню</b>")
        lines.append(" · ".join(esc(label) for label in spec.menu_buttons))
        lines.append("")

    if spec.commands:
        lines.append("<b>Команды</b>")
        for cmd in spec.commands:
            lines.append(f"/{esc(cmd.command)} — {esc(cmd.description)}")
        lines.append("")

    if spec.triggers:
        lines.append(f"<b>Ответы на частые вопросы</b>: {len(spec.triggers)}")
        lines.append("")

    if spec.ai.enabled:
        lines.append(f"<b>Свободное общение</b>: включено ({esc(spec.ai.persona)})")
    else:
        lines.append("<b>Свободное общение</b>: выключено")

    return "\n".join(lines).strip()


def strict_json_schema() -> dict[str, Any]:
    """JSON-схема BotSpec с additionalProperties: false во всех объектах."""
    schema = BotSpec.model_json_schema()

    def tighten(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node.setdefault("required", list(node["properties"].keys()))
            for value in node.values():
                tighten(value)
        elif isinstance(node, list):
            for value in node:
                tighten(value)

    tighten(schema)
    return schema
