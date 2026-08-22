"""Шифрование чужих токенов перед записью в базу."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class DecryptError(RuntimeError):
    """Токен не расшифровывается — скорее всего сменился FERNET_KEY."""


def generate_key() -> str:
    """Новый ключ шифрования для .env."""
    return Fernet.generate_key().decode()


class TokenCipher:
    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode())
        except (ValueError, TypeError) as exc:
            raise RuntimeError(
                "FERNET_KEY выглядит неправильно. Сгенерируйте новый: python -m botfactory.crypto"
            ) from exc

    def encrypt(self, raw: str) -> str:
        return self._fernet.encrypt(raw.encode()).decode()

    def decrypt(self, encrypted: str) -> str:
        try:
            return self._fernet.decrypt(encrypted.encode()).decode()
        except InvalidToken as exc:
            raise DecryptError(
                "Не удалось расшифровать токен. Похоже, FERNET_KEY в .env изменился "
                "после того, как бот был сохранён."
            ) from exc


if __name__ == "__main__":
    print(generate_key())
