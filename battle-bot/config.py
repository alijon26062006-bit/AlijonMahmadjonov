"""Настройки бота. Всё читается из переменных окружения (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import time
from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")


def _env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Не задана переменная окружения {name}")
    return value


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _env_ids(name: str) -> list[int]:
    raw = os.getenv(name, "").replace(";", ",")
    return [int(part) for part in raw.split(",") if part.strip()]


def _parse_times(raw: str) -> list[time]:
    """'18:00,19:30,21:00' -> [time(18, 0), time(19, 30), time(21, 0)]"""
    result: list[time] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        hours, _, minutes = chunk.partition(":")
        result.append(time(int(hours), int(minutes or 0)))
    if not result:
        raise RuntimeError("ROUND_TIMES пуст — нужно хотя бы одно время подведения итогов")
    return result


@dataclass(frozen=True)
class VotePack:
    """Пакет голосов за звёзды."""

    votes: int
    stars: int

    @property
    def title(self) -> str:
        return f"{self.votes} голосов"


@dataclass
class Config:
    bot_token: str
    bot_username: str        # пусто -> спросим у Telegram при запуске
    channel_id: int          # -100... — куда постим пары
    channel_url: str         # пусто -> возьмём из данных канала
    admin_ids: list[int]

    db_path: str
    round_times: list[time]  # дедлайны раундов по МСК, по порядку
    min_participants: int
    max_participants: int

    require_subscription: bool
    require_username: bool
    paid_votes_enabled: bool
    vote_packs: list[VotePack]

    referral_enabled: bool
    referral_reward: int      # голосов за одного приглашённого
    premium_emoji_file: str  # JSON «символ -> emoji_id», пусто -> обычные эмодзи
    premium_emoji_in_channel: str   # "auto" | "1" | "0", см. services/emoji.py
    prizes: list[str]        # призы за 1/2/3 место: число — звёзды, текст — как есть
    publish_delay: float     # пауза между постами, чтобы не ловить лимиты Telegram
    dm_delay: float          # пауза между личными сообщениями при рассылке

    # живая таблица «символ -> emoji_id»: заполняется при старте,
    # пополняется командой /emojiset без перезапуска
    premium_emoji: dict[str, str] = field(default_factory=dict)

    @property
    def deadline_count(self) -> int:
        return len(self.round_times)


def load_config() -> Config:
    packs_raw = os.getenv("VOTE_PACKS", "1:15,5:60,10:100")
    packs = []
    for chunk in packs_raw.split(","):
        votes, _, stars = chunk.strip().partition(":")
        if votes:
            packs.append(VotePack(int(votes), int(stars)))

    from services.prizes import parse as parse_prizes

    prizes = parse_prizes(os.getenv("PRIZES", "1000,500,250"))

    return Config(
        bot_token=_env("BOT_TOKEN"),
        bot_username=os.getenv("BOT_USERNAME", "").lstrip("@"),
        channel_id=int(_env("CHANNEL_ID")),
        channel_url=os.getenv("CHANNEL_URL", ""),
        admin_ids=_env_ids("ADMIN_IDS"),
        db_path=os.getenv("DB_PATH", "battle.db"),
        round_times=_parse_times(os.getenv("ROUND_TIMES", "18:00,19:30,21:00,22:15,23:30")),
        min_participants=_env_int("MIN_PARTICIPANTS", 4),
        max_participants=_env_int("MAX_PARTICIPANTS", 512),
        require_subscription=os.getenv("REQUIRE_SUBSCRIPTION", "1") == "1",
        require_username=os.getenv("REQUIRE_USERNAME", "1") == "1",
        paid_votes_enabled=os.getenv("PAID_VOTES", "1") == "1",
        vote_packs=packs,
        referral_enabled=os.getenv("REFERRALS", "1") == "1",
        referral_reward=_env_int("REFERRAL_REWARD", 1),
        premium_emoji_file=os.getenv("PREMIUM_EMOJI_FILE", "premium_emoji.json"),
        premium_emoji_in_channel=os.getenv("PREMIUM_EMOJI_IN_CHANNEL", "auto").lower(),
        prizes=prizes,
        publish_delay=float(os.getenv("PUBLISH_DELAY", "1.0")),
        dm_delay=float(os.getenv("DM_DELAY", "0.05")),
    )
