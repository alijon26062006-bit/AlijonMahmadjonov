"""Реестр игр. Всё, что различает игры, собрано здесь — остальной код
работает с матчем и роботом, не зная, какая именно игра идёт.

Добавить игру — значит добавить строку в GAMES и два класса: матч и робот.
"""

from __future__ import annotations

from dataclasses import dataclass

from .game import Match, Side
from .robot import ROBOT_ID, Robot
from .sea_match import SeaMatch, SeaSide
from .sea_robot import SeaRobot

ROPE = "rope"
SEA = "sea"
DEFAULT_GAME = ROPE


@dataclass(frozen=True)
class GameInfo:
    """Что нужно знать об игре, не зная её правил."""

    id: str
    match_cls: type
    side_cls: type
    robot_cls: type
    # Длительность матча по умолчанию: 0 — до победы.
    duration: int
    # Значок игры в текстах бота.
    icon: str = "⚔️"


GAMES: dict[str, GameInfo] = {
    ROPE: GameInfo(id=ROPE, match_cls=Match, side_cls=Side, robot_cls=Robot, duration=60, icon="🪢"),
    SEA: GameInfo(id=SEA, match_cls=SeaMatch, side_cls=SeaSide, robot_cls=SeaRobot, duration=0, icon="🚢"),
}

GAME_IDS = tuple(GAMES)


def normalize(game: str | None) -> str:
    """Имя игры из чего угодно. Незнакомое — канат: он был первым."""

    name = (game or "").strip().lower()
    return name if name in GAMES else DEFAULT_GAME


def info(game: str | None) -> GameInfo:
    return GAMES[normalize(game)]


def make_side(game: str, **fields) -> Side:
    return info(game).side_cls(**fields)


def robot_side(game: str, name: str, rating: int) -> Side:
    return make_side(game, user_id=ROBOT_ID, name=name, rating=rating, is_bot=True)


def make_match(game: str, a: Side, b: Side, **fields) -> Match:
    return info(game).match_cls(a=a, b=b, **fields)


def make_robot(game: str, speed: str, seed: int | None = None):
    return info(game).robot_cls(speed=speed, seed=seed)
