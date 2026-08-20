"""Модели предметной области. Никакой зависимости от Telegram и БД."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BattleStatus(str, Enum):
    REGISTRATION = "registration"  # приём заявок, пары публикуются по мере набора
    RUNNING = "running"            # идут раунды 2+
    FINISHED = "finished"
    CANCELLED = "cancelled"


class MatchStatus(str, Enum):
    VOTING = "voting"
    CLOSED = "closed"


class ParticipantStatus(str, Enum):
    ALIVE = "alive"
    OUT = "out"


class VoteSource(str, Enum):
    FREE = "free"
    PAID = "paid"


@dataclass(frozen=True)
class Player:
    """Участник батла в терминах логики сетки."""

    user_id: int
    nickname: str

    def mention(self) -> str:
        return f"@{self.nickname}" if not self.nickname.startswith("@") else self.nickname


@dataclass
class Slot:
    """Один участник внутри матча вместе с его счётом."""

    user_id: int
    nickname: str
    votes: int = 0
    position: int = 0  # порядковый номер в матче, с 1


@dataclass
class MatchResult:
    """Итог одного матча после закрытия голосования."""

    match_id: int
    ranking: list[Slot]          # отсортировано: первый — победитель
    winners: list[int]           # user_id тех, кто проходит дальше
    losers: list[int]
    tie_broken: bool = False     # победитель определён жребием


@dataclass
class RoundPlan:
    """Что публикуем в очередном раунде."""

    round_no: int
    groups: list[list[Player]] = field(default_factory=list)
    byes: list[Player] = field(default_factory=list)
    is_final: bool = False

    @property
    def match_count(self) -> int:
        return len(self.groups)
