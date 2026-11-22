"""SSH-ключ панели и смена root-пароля на сервере.

Если создать сервер без SSH-ключа, Hetzner пришлёт root-пароль на почту владельца
аккаунта и потребует сменить его при первом входе. Поэтому сервер создаётся с
ключом панели (RSA 3072, файл 600), а пароль клиента панель ставит сама по SSH:
chpasswd (пароль только через stdin) и chage -d сегодня — смена не потребуется.
Пароль нигде не хранится.
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
import time
from pathlib import Path

import paramiko

from .hetzner import Hetzner, HetznerError

log = logging.getLogger(__name__)


def ensure_key(path: Path) -> paramiko.RSAKey:
    if path.exists():
        return paramiko.RSAKey.from_private_key_file(str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    key = paramiko.RSAKey.generate(3072)
    buf = io.StringIO()
    key.write_private_key(buf)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(buf.getvalue())
    return key


def public_line(key: paramiko.RSAKey) -> str:
    return f"{key.get_name()} {key.get_base64()} vps-panel"


def key_name(key: paramiko.RSAKey) -> str:
    return "vps-panel-" + hashlib.sha256(key.get_base64().encode()).hexdigest()[:10]


async def ensure_registered(h: Hetzner, key: paramiko.RSAKey) -> str:
    """Ключ панели в проекте Hetzner: найти по имени, иначе добавить."""
    name = key_name(key)
    found = (await h.get("/ssh_keys", {"name": name})).get("ssh_keys") or []
    if found:
        return name
    try:
        await h.post("/ssh_keys", {"name": name, "public_key": public_line(key),
                                   "labels": {"managed-by": "vps-panel"}})
    except HetznerError as exc:
        if exc.code != "uniqueness_error":   # такой ключ уже есть под другим именем
            raise
        for item in await h.list("/ssh_keys", "ssh_keys"):
            if item.get("public_key", "").split()[:2] == public_line(key).split()[:2]:
                return item["name"]
        raise
    return name


class SSHFailed(Exception):
    pass


def set_root_password(ip: str, password: str, *, key: paramiko.RSAKey | None = None,
                      login_password: str | None = None, attempts: int = 30, pause: float = 10.0) -> None:
    """Зайти по SSH (ключом панели или выданным паролем) и поставить root-пароль.

    Сервер после создания ещё грузится — пробуем несколько раз.
    """
    last = ""
    for _ in range(max(attempts, 1)):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(ip, username="root", pkey=key, password=login_password, timeout=15,
                           banner_timeout=20, auth_timeout=20, allow_agent=False, look_for_keys=False)
            stdin, stdout, stderr = client.exec_command("chpasswd", timeout=30)
            stdin.write(f"root:{password}\n")
            stdin.flush()
            stdin.channel.shutdown_write()
            if stdout.channel.recv_exit_status() != 0:
                raise SSHFailed("chpasswd: " + stderr.read().decode(errors="replace")[:200])
            _, out, err = client.exec_command('chage -d "$(date +%Y-%m-%d)" root', timeout=30)
            if out.channel.recv_exit_status() != 0:
                raise SSHFailed("chage: " + err.read().decode(errors="replace")[:200])
            return
        except paramiko.AuthenticationException as exc:
            raise SSHFailed(f"ключ не подошёл: {exc}") from exc
        except SSHFailed:
            raise
        except Exception as exc:  # noqa: BLE001 — сервер ещё не поднялся
            last = str(exc)
            time.sleep(pause)
        finally:
            client.close()
    raise SSHFailed(f"SSH недоступен: {last}")
