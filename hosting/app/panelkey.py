"""SSH-ключ панели.

Передаётся Hetzner при создании серверов. Тогда Hetzner не ставит свой временный root-пароль,
не присылает его вам на почту и не заставляет клиента менять пароль при первом входе.
Пароль клиента панель ставит сама, заходя на сервер по этому ключу.
"""
from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path

import paramiko

_lock = threading.Lock()


class PanelKey:
    def __init__(self, directory: str | Path):
        self.path = Path(directory) / "panel_ssh_key"
        self._key: paramiko.PKey | None = None

    def load(self) -> paramiko.PKey:
        with _lock:
            if self._key is not None:
                return self._key
            if self.path.exists():
                self._key = paramiko.RSAKey.from_private_key_file(str(self.path))
            else:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                key = paramiko.RSAKey.generate(3072)
                tmp = self.path.with_suffix(".tmp")
                key.write_private_key_file(str(tmp))
                os.chmod(tmp, 0o600)
                os.replace(tmp, self.path)
                self._key = key
            return self._key

    @property
    def public_line(self) -> str:
        key = self.load()
        return f"{key.get_name()} {key.get_base64()} averix-panel"

    @property
    def name(self) -> str:
        """Имя ключа в Hetzner: уникально для этого ключа, чтобы не спутать с чужими."""
        digest = hashlib.sha256(self.load().get_base64().encode()).hexdigest()[:10]
        return f"averix-panel-{digest}"
