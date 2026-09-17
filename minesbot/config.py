"""Настройки мина-бота.

Всё, что нельзя хранить в коде (токен), и всё, что хочется менять без правки
кода (ставки, число мин, комиссия), живёт в переменных окружения / файле .env.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Файл .env читается, если стоит python-dotenv. Без него просто берём окружение.
try:  # pragma: no cover - зависит от окружения
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):  # type: ignore[misc]
        return False


class ConfigError(RuntimeError):
    """Настройки заданы неверно — запускаться нельзя."""


# Поле 5x5. Меняешь здесь — меняется и математика выплат.
CELLS = 25
ROW = 5


@dataclass(frozen=True)
class Config:
    token: str
    db_path: Path
    admin_ids: frozenset[int]
    start_balance: int
    bonus_amount: int
    bonus_hours: int
    min_bet: int
    max_bet: int
    default_mines: int
    house_edge: float
    log_level: str


def _int(name: str, default: int, *, low: int | None = None, high: int | None = None) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} должно быть целым числом, а там «{raw}».") from None
    if low is not None and value < low:
        raise ConfigError(f"{name} не может быть меньше {low} (сейчас {value}).")
    if high is not None and value > high:
        raise ConfigError(f"{name} не может быть больше {high} (сейчас {value}).")
    return value


def _ids(name: str) -> frozenset[int]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return frozenset()
    out: set[int] = set()
    for chunk in raw.replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            out.add(int(chunk))
        except ValueError:
            raise ConfigError(f"{name}: «{chunk}» не похоже на telegram id.") from None
    return frozenset(out)


# Свой файл идёт первым: в репозитории рядом живёт другой бот со своим .env,
# и его ключи трогать нельзя.
ENV_FILES = (".env.mines", ".env")


def load(env_file: str | os.PathLike[str] | None = "auto") -> Config:
    """Собрать настройки. Бросает ConfigError с понятным текстом, если что-то не так.

    env_file="auto" — прочитать .env.mines, затем .env; None — только окружение.
    """

    if env_file == "auto":
        for candidate in ENV_FILES:
            if Path(candidate).is_file():
                load_dotenv(candidate, override=False)
    elif env_file:
        load_dotenv(env_file, override=False)

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise ConfigError(
            "Не задан TELEGRAM_BOT_TOKEN. Возьми токен у @BotFather и положи его в .env"
        )
    # Формат токена: <цифры>:<буквы-цифры>. Проверяем заранее, чтобы не ловить
    # невнятный 401 от Telegram уже в работе.
    head, _, tail = token.partition(":")
    if not head.isdigit() or len(tail) < 30:
        raise ConfigError(
            "TELEGRAM_BOT_TOKEN не похож на токен. Он выглядит так: 123456789:AA...."
        )

    mines = _int("MINES_COUNT", 3, low=1, high=CELLS - 1)
    min_bet = _int("MIN_BET", 10, low=1)
    max_bet = _int("MAX_BET", 100_000, low=1)
    if min_bet > max_bet:
        raise ConfigError(f"MIN_BET ({min_bet}) больше MAX_BET ({max_bet}).")

    try:
        edge = float(os.getenv("HOUSE_EDGE", "0.03"))
    except ValueError:
        raise ConfigError("HOUSE_EDGE должно быть числом, например 0.03") from None
    if not 0.0 <= edge < 0.5:
        raise ConfigError("HOUSE_EDGE должно быть от 0 до 0.5 (0.03 = комиссия 3%).")

    data_dir = Path(os.getenv("DATA_DIR", "data")).expanduser()

    return Config(
        token=token,
        db_path=data_dir / "mines.db",
        admin_ids=_ids("ADMIN_IDS"),
        start_balance=_int("START_BALANCE", 1_000, low=0),
        bonus_amount=_int("BONUS_AMOUNT", 500, low=0),
        bonus_hours=_int("BONUS_HOURS", 12, low=1),
        min_bet=min_bet,
        max_bet=max_bet,
        default_mines=mines,
        house_edge=edge,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
