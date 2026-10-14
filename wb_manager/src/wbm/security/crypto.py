"""Шифрование токенов WB (Fernet). Ключи — только в .env, не в базе и не в git.

Поддерживается смена ключа: FERNET_KEYS=новый,старый — расшифровываются оба,
шифруется новым; `rotate` перешифровывает старые записи.
"""

from __future__ import annotations

from collections.abc import Sequence

from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class CryptoConfigError(Exception):
    """Ключ шифрования не задан или неверного формата."""


class TokenDecryptError(Exception):
    """Не удалось расшифровать: запись повреждена или ключ сменили без старого ключа."""


class TokenCipher:
    def __init__(self, keys: Sequence[str]) -> None:
        cleaned = [key.strip() for key in keys if key.strip()]
        if not cleaned:
            raise CryptoConfigError("Не задан ключ шифрования FERNET_KEYS")
        try:
            self._fernet = MultiFernet([Fernet(key.encode()) for key in cleaned])
        except (ValueError, TypeError):
            raise CryptoConfigError(
                "Неверный ключ FERNET_KEYS: нужен ключ Fernet (32 байта в base64)"
            ) from None

    @classmethod
    def from_setting(cls, value: str) -> TokenCipher:
        """Из строки настроек: ключи через запятую, первый — текущий."""
        return cls(value.split(","))

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            raise TokenDecryptError("Не удалось расшифровать токен") from None

    def rotate(self, ciphertext: str) -> str:
        try:
            return self._fernet.rotate(ciphertext.encode()).decode()
        except InvalidToken:
            raise TokenDecryptError("Не удалось перешифровать токен") from None


def generate_key() -> str:
    return Fernet.generate_key().decode()
