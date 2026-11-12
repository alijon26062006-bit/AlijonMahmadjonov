"""Установка root-пароля, который выбрал клиент.

Hetzner по API умеет только сбросить пароль на случайный. Поэтому:
1) сбрасываем через API и получаем временный пароль;
2) заходим по SSH с этим паролем и ставим пароль клиента через chpasswd (по stdin, не в командной строке).

Ключ хоста запоминается при первом подключении (TOFU): если позже он изменится,
подключение будет отклонено — так нельзя подсунуть чужой сервер.
"""
from __future__ import annotations

import base64
import time

import paramiko


class SshError(Exception):
    pass


class SshAuthError(SshError):
    """Сервер не принял ни ключ панели, ни пароль — нужен резервный способ."""


class _Tofu(paramiko.MissingHostKeyPolicy):
    def __init__(self, expected: str):
        self.expected = expected
        self.seen = ""

    def missing_host_key(self, client, hostname, key):
        fp = f"{key.get_name()} {base64.b64encode(key.asbytes()).decode()}"
        if self.expected and fp != self.expected:
            raise SshError("Ключ SSH сервера изменился. Если вы переустанавливали ОС, обратитесь в поддержку.")
        self.seen = fp


def set_root_password(host: str, current_password: str | None, new_password: str, *, known_hostkey: str = "",
                      pkey: paramiko.PKey | None = None, attempts: int = 10, delay: float = 6.0,
                      timeout: float = 15.0, port: int = 22) -> str:
    """Ставит root-пароль: входит по ключу панели (pkey) или по текущему паролю.

    Возвращает отпечаток ключа хоста (для сохранения). Бросает SshAuthError, если вход не принят,
    и SshError при остальных ошибках.
    """
    if not host:
        raise SshError("У сервера ещё нет IP-адреса")
    # chpasswd делит строку по первому «:», поэтому двоеточие в самом пароле допустимо.
    if any(ch in new_password for ch in "\n\r\0"):
        raise SshError("Пароль содержит недопустимые символы")
    last = ""
    for i in range(attempts):
        client = paramiko.SSHClient()
        policy = _Tofu(known_hostkey)
        client.set_missing_host_key_policy(policy)
        try:
            client.connect(host, port=port, username="root", password=current_password, pkey=pkey, timeout=timeout,
                           auth_timeout=timeout, banner_timeout=timeout, look_for_keys=False, allow_agent=False)
            # chage: пароль считается только что сменённым — система не потребует сменить его при входе.
            stdin, stdout, stderr = client.exec_command(
                'chpasswd && (chage -d "$(date +%Y-%m-%d)" root 2>/dev/null || true)', timeout=timeout)
            stdin.write(f"root:{new_password}\n")
            stdin.channel.shutdown_write()
            code = stdout.channel.recv_exit_status()
            if code != 0:
                raise SshError("chpasswd завершился с ошибкой: " + stderr.read().decode(errors="replace")[:200])
            return policy.seen or known_hostkey
        except SshError:
            raise
        except paramiko.AuthenticationException:
            # Сразу после загрузки ключ или пароль может появиться не мгновенно — пробуем ещё.
            last = "auth"
        except Exception as e:  # noqa: BLE001 — сеть, таймауты, sshd ещё не поднялся
            last = f"{e.__class__.__name__}"
        finally:
            client.close()
        if i < attempts - 1:
            time.sleep(delay)
    if last == "auth":
        raise SshAuthError("Сервер не принял вход по SSH (ключ панели удалён или вход по паролю отключён)")
    raise SshError(f"Не удалось подключиться по SSH: {last}")
