"""Deep-links в бота и ссылки на посты канала."""
from __future__ import annotations

VOTE_PREFIX = "v"
REF_PREFIX = "r"
JOIN_PAYLOAD = "join"


def vote_link(bot_username: str, match_id: int) -> str:
    """Ссылка, которая открывает бота сразу на экране голосования этого матча.

    Её участник рассылает своим — по ней приходят голосовать именно за его пару.
    """
    return f"https://t.me/{bot_username}?start={VOTE_PREFIX}{match_id}"


def join_link(bot_username: str) -> str:
    return f"https://t.me/{bot_username}?start={JOIN_PAYLOAD}"


def invite_link(bot_username: str, user_id: int) -> str:
    """Личная ссылка-приглашение: за друга по ней начисляется голос."""
    return f"https://t.me/{bot_username}?start={REF_PREFIX}{user_id}"


def post_link(channel_id: int, message_id: int) -> str:
    """Ссылка на пост в канале. Работает и для приватных каналов (формат /c/)."""
    raw = str(channel_id)
    internal = raw[4:] if raw.startswith("-100") else raw.lstrip("-")
    return f"https://t.me/c/{internal}/{message_id}"


def public_post_link(channel_url: str, message_id: int) -> str:
    return f"{channel_url.rstrip('/')}/{message_id}"


def parse_start_payload(payload: str | None) -> tuple[str, int | None]:
    """Разобрать аргумент /start.

    Возвращает ('vote', match_id) | ('ref', inviter_id) | ('join', None)
    | ('plain', None).
    """
    if not payload:
        return "plain", None
    payload = payload.strip()
    if payload == JOIN_PAYLOAD:
        return "join", None
    if payload.startswith(VOTE_PREFIX) and payload[1:].isdigit():
        return "vote", int(payload[1:])
    if payload.startswith(REF_PREFIX) and payload[1:].isdigit():
        return "ref", int(payload[1:])
    return "plain", None
