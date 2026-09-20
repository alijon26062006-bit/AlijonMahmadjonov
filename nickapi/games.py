"""Список игр, по которым можно проверить ник.

Ключ игры — короткое слово для URL (`?game=ff`). Для FireLoot важен только
`sku`: он определяет игру и регион, сам товар при проверке не покупается,
поэтому берём самый дешёвый пакет.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Game:
    key: str            # что писать в ?game=
    title: str          # человеческое название
    sku: str            # любой sku этой игры — нужен эндпоинту /validate
    id_label: str       # что просить у пользователя
    needs_server: bool = False   # нужен ли номер сервера (Mobile Legends)
    telegram: bool = False       # проверка через /telegram/check, а не /validate


GAMES: tuple[Game, ...] = (
    Game("ff",       "Free Fire (СНГ)",       "diamonds_110",        "ID игрока"),
    Game("ffid",     "Free Fire (Индонезия)", "id_diamonds_50",      "ID игрока"),
    Game("pubg",     "PUBG Mobile",           "pubg_uc_60",          "ID игрока"),
    Game("mlbb",     "Mobile Legends",        "mlbb_diamonds_32",    "ID игрока", needs_server=True),
    Game("mlbbcis",  "Mobile Legends (СНГ)",  "mlbbcis_diamonds_50", "ID игрока", needs_server=True),
    Game("hok",      "Honor of Kings",        "hok_tokens_16",       "ID игрока"),
    Game("bs",       "Blood Strike",          "bs_gold_51",          "ID игрока"),
    Game("mr",       "Marvel Rivals",         "mr_lattice_100",      "ID игрока"),
    Game("tg",       "Telegram (Stars)",      "",                    "username", telegram=True),
)

BY_KEY: dict[str, Game] = {g.key: g for g in GAMES}

# Синонимы: чтобы чужой проект мог слать привычные ему названия.
ALIASES: dict[str, str] = {
    "freefire": "ff", "ff_cis": "ff", "ffcis": "ff",
    "ff_id": "ffid", "freefire_id": "ffid", "indonesia": "ffid",
    "pubgm": "pubg", "pubg_mobile": "pubg", "uc": "pubg",
    "ml": "mlbb", "mobilelegends": "mlbb", "mobile_legends": "mlbb",
    "ml_cis": "mlbbcis", "mlcis": "mlbbcis",
    "honorofkings": "hok", "honor_of_kings": "hok",
    "bloodstrike": "bs", "blood_strike": "bs",
    "marvelrivals": "mr", "marvel_rivals": "mr",
    "telegram": "tg", "stars": "tg", "tg_stars": "tg",
}


def find(key: str) -> Game | None:
    """Ищет игру по ключу или синониму, регистр не важен."""
    k = (key or "").strip().lower().replace("-", "_")
    return BY_KEY.get(k) or BY_KEY.get(ALIASES.get(k, ""))


def listing() -> list[dict]:
    """Описание всех игр — отдаётся на GET /games."""
    return [
        {
            "game": g.key,
            "title": g.title,
            "id_label": g.id_label,
            "needs_server": g.needs_server,
        }
        for g in GAMES
    ]
