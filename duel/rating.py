"""Рейтинг Эло: чем сильнее соперник, тем дороже победа над ним."""

from __future__ import annotations

START_RATING = 1000
MIN_RATING = 100

# Новичку рейтинг двигается резко, чтобы он быстро нашёл свой уровень,
# а у опытного игрока — плавно, чтобы одна случайная партия ничего не решала.
K_NEW = 40
K_NORMAL = 24
K_STRONG = 16
NEW_GAMES = 15
STRONG_RATING = 1600


def k_factor(rating: int, games: int) -> int:
    if games < NEW_GAMES:
        return K_NEW
    if rating >= STRONG_RATING:
        return K_STRONG
    return K_NORMAL


def expected(rating: int, opponent: int) -> float:
    """Вероятность победы по Эло."""

    return 1.0 / (1.0 + 10 ** ((opponent - rating) / 400.0))


def update(
    rating: int,
    opponent: int,
    score: float,
    games: int = 0,
) -> int:
    """Новый рейтинг. score: 1 — победа, 0.5 — ничья, 0 — поражение."""

    delta = k_factor(rating, games) * (score - expected(rating, opponent))
    return max(MIN_RATING, round(rating + delta))


def both(
    rating_a: int,
    rating_b: int,
    winner: str,
    games_a: int = 0,
    games_b: int = 0,
) -> tuple[int, int]:
    """Пересчёт для обоих сразу. winner: 'a', 'b' или 'draw'."""

    score_a = {"a": 1.0, "b": 0.0}.get(winner, 0.5)
    return (
        update(rating_a, rating_b, score_a, games_a),
        update(rating_b, rating_a, 1.0 - score_a, games_b),
    )


def title(rating: int) -> str:
    """Звание по рейтингу — показывается в профиле и в таблице."""

    for bound, name in (
        (800, "новичок"),
        (1000, "ученик"),
        (1200, "счетовод"),
        (1400, "мастер"),
        (1600, "снайпер"),
        (1800, "гроссмейстер"),
    ):
        if rating < bound:
            return name
    return "легенда"
