"""Муҳофиз аз нусхаи дуюми бот.

Ду нусхаи бот бо як токен ва як базаи ибтидоӣ харидоронро байни худ тақсим
мекунанд, пулро дар ду базаи гуногун менависанд ва рақамҳои фармоишашон
якхела мешаванд. Ин модул се чизро месанҷад:

*   дар ҳамин сервер нусхаи дигари ҳамин бот аллакай кор мекунад (қулф);
*   ин сервер пас аз кӯчидан бояд хомӯш бошад (нишонаи ``MOVED_TO``);
*   номи сервер ва папка — то админ бубинад, бот аз куҷо сар шуд.
"""

from __future__ import annotations

import fcntl
import hashlib
import os
import socket
import tempfile
from pathlib import Path

#: Коди баромад: бот худаш сар нашуд — systemd онро аз нав оғоз намекунад.
EXIT_REFUSED = 3

MOVED_FILE = "MOVED_TO"


class StartRefused(RuntimeError):
    """Бот набояд дар ин ҷо сар шавад."""


def token_tag(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:12]


def lock_dir() -> Path:
    """/run/lock тоза карда намешавад (дар /tmp файлҳои кӯҳнаро система пок мекунад)."""
    run_lock = Path("/run/lock")
    if run_lock.is_dir() and os.access(run_lock, os.W_OK):
        return run_lock
    return Path(tempfile.gettempdir())


def lock_path(token: str) -> Path:
    return lock_dir() / f"almaz-shop-{token_tag(token)}.lock"


def acquire_instance_lock(token: str, where: Path):
    """Қулфи «танҳо як нусха дар сервер». Файлро то охири кори бот нигоҳ доред."""
    path = lock_path(token)
    handle = open(path, "a+", encoding="utf-8")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.seek(0)
        owner = handle.read().strip() or "номаълум"
        handle.close()
        raise StartRefused(
            "Дар ҳамин сервер нусхаи дигари ҳамин бот аллакай кор мекунад "
            f"({owner}). Ду нусха харидоронро тақсим мекунанд ва пул гум мешавад. "
            "Ҳамаи нусхаҳоро бинед:  bot doctor"
        ) from None
    handle.seek(0)
    handle.truncate()
    handle.write(f"pid={os.getpid()} папка={where}\n")
    handle.flush()
    return handle


def moved_to(data_dir: Path) -> str | None:
    """Агар бот аз ин ҷо ба сервери дигар кӯчида бошад — куҷо."""
    try:
        text = (Path(data_dir) / MOVED_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or "сервери дигар"


def mark_moved(data_dir: Path, where: str) -> None:
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    (Path(data_dir) / MOVED_FILE).write_text(where + "\n", encoding="utf-8")


def check_not_moved(data_dir: Path) -> None:
    target = moved_to(data_dir)
    if target:
        raise StartRefused(
            f"Бот аз ин сервер кӯчонида шудааст ({target}). Нусхаи дуюм пулро "
            "дар базаи дигар менавишт, бинобар ин ин ҷо сар намешавад. Агар воқеан "
            f"ҳамин ҷо кор кардан лозим бошад:  rm {Path(data_dir) / MOVED_FILE}"
        )


def host_label() -> str:
    """«uways (2.29.11.118)» — барои хабари админ."""
    name = socket.gethostname()
    ip = ""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))     # ҳеҷ чиз фиристода намешавад
            ip = probe.getsockname()[0]
    except OSError:
        pass
    return f"{name} ({ip})" if ip else name
