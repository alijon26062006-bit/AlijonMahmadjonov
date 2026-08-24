"""Чистка группы от спама.

Работает **только в группах**, куда бота добавили администратором. Каналы —
главный и канал батлов — этот модуль не трогает вообще: там пишет сам бот.

Правила намеренно простые и объяснимые: за каждое удаление бот может назвать
причину. Умных моделей здесь не нужно — спам в маленькой группе всегда
выглядит одинаково: ссылка, пересылка с канала или набор слов из списка.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ссылки в любом виде, включая t.me и голый домен
LINK = re.compile(
    r"(https?://|www\.|t\.me/|telegram\.me/|"
    r"\b[a-z0-9-]+\.(com|net|org|ru|io|xyz|top|site|online|shop|club|link)\b)",
    re.IGNORECASE,
)
# @упоминание чужого канала или бота
MENTION = re.compile(r"@[a-zA-Z][a-zA-Z0-9_]{4,}")

# Стартовый список. Он не претендует на полноту — админ правит его в панели
# под свою группу. Слова ищутся по вхождению, поэтому «казино» поймает и
# «казиношка».
DEFAULT_WORDS = (
    "18+,порно,porn,интим,эскорт,шлюх,секс досуг,"
    "казино,ставки на спорт,букмекер,1xbet,мелбет,"
    "взлом,взломать,накрутка подписчиков,слив базы,скам,"
    "крипта заработок,инвестиции под,пассивный доход,"
    "заработок от,в день от,работа в телеграм,курьер,закладк"
)


@dataclass(frozen=True)
class Verdict:
    """Что сделать с сообщением и почему."""

    delete: bool
    reason: str = ""

    def __bool__(self) -> bool:
        return self.delete


CLEAN = Verdict(delete=False)


def words(raw: str) -> list[str]:
    """Разобрать список запрещённых слов из настройки."""
    return [w.strip().lower() for w in (raw or "").replace(";", ",").split(",") if w.strip()]


def text_of(message) -> str:
    """Весь текст сообщения: и подпись к медиа тоже."""
    return " ".join(
        part for part in (
            getattr(message, "text", None),
            getattr(message, "caption", None),
        ) if part
    )


def has_link(message) -> bool:
    """Ссылка в тексте или спрятанная в разметке.

    Проверять только текст мало: ссылку прячут в подпись слова через
    text_link, и в самом тексте её тогда не видно.
    """
    if LINK.search(text_of(message)):
        return True
    entities = list(getattr(message, "entities", None) or [])
    entities += list(getattr(message, "caption_entities", None) or [])
    return any(entity.type in {"url", "text_link"} for entity in entities)


def forwarded_from_channel(message) -> bool:
    origin = getattr(message, "forward_origin", None)
    chat = getattr(origin, "chat", None)
    return chat is not None and getattr(chat, "type", None) == "channel"


def check(message, settings, is_new: bool = False) -> Verdict:
    """Что делать с сообщением из группы.

    ``is_new`` — человек только что вошёл в группу. Новичок со ссылкой это
    почти всегда спам, поэтому для него правило строже.
    """
    body = text_of(message).lower()

    for word in words(settings.get("spam_words")):
        if word and word in body:
            return Verdict(True, f"запрещённое слово «{word}»")

    if getattr(message, "via_bot", None) is not None and settings.get("spam_delete_links"):
        return Verdict(True, "сообщение через стороннего бота")

    if forwarded_from_channel(message) and settings.get("spam_delete_forwards"):
        return Verdict(True, "пересылка из канала")

    if has_link(message):
        if settings.get("spam_delete_links"):
            return Verdict(True, "ссылка")
        if is_new:
            return Verdict(True, "ссылка от новичка")

    mentions = MENTION.findall(text_of(message))
    limit = int(settings.get("spam_mention_limit") or 0)
    if limit and len(mentions) > limit:
        return Verdict(True, f"упоминаний больше {limit}")

    return CLEAN
