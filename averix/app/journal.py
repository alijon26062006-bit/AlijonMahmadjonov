"""
Журнал важных событий.

Пишем в стандартный вывод: службой управляет systemd, поэтому строки
попадают в журнал системы и читаются через `journalctl -u averix`.
Своего файла нет намеренно — не нужно следить за его размером и правами.

Чего в журнале не будет никогда: паролей, токенов сессий, cookie
и содержимого CSRF-токенов. За этим следит _SECRET_KEYS: попытка
записать такое поле заменяется на «скрыто», а не молча проходит.
"""
import logging
import sys

logger = logging.getLogger("averix")

# Имена, значения которых не попадают в журнал ни при каких условиях
_SECRET_KEYS = frozenset({
    "password", "pass", "pwd", "secret", "token", "csrf", "cookie",
    "session", "authorization", "api_key", "apikey", "hash",
})


def setup(debug: bool = False) -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s",
                                           datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False


def _clean(key: str, value) -> str:
    if any(bad in key.lower() for bad in _SECRET_KEYS):
        return "скрыто"
    text = str(value)
    # Переводы строк ломают разбор журнала и позволяют подделать
    # соседнюю запись, если значение пришло от пользователя
    text = text.replace("\n", " ").replace("\r", " ")
    return text[:200]


def event(action: str, level: int = logging.INFO, **fields) -> None:
    parts = [action]
    for key, value in fields.items():
        if value is None or value == "":
            continue
        parts.append(f"{key}={_clean(key, value)}")
    logger.log(level, " ".join(parts))


def warn(action: str, **fields) -> None:
    event(action, logging.WARNING, **fields)


def error(action: str, **fields) -> None:
    event(action, logging.ERROR, **fields)
