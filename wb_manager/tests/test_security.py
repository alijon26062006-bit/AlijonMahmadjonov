from __future__ import annotations

import pytest

from tests.helpers import personal_token
from wbm.security.crypto import CryptoConfigError, TokenCipher, TokenDecryptError, generate_key
from wbm.security.passwords import (
    WeakPasswordError,
    hash_password,
    needs_rehash,
    verify_password,
)


def test_token_roundtrip_and_ciphertext_hides_token() -> None:
    cipher = TokenCipher([generate_key()])
    token = personal_token()

    encrypted = cipher.encrypt(token)

    assert token not in encrypted
    assert cipher.decrypt(encrypted) == token
    assert cipher.encrypt(token) != encrypted  # у каждого шифрования своя соль


def test_key_rotation() -> None:
    old_key, new_key = generate_key(), generate_key()
    old_cipher = TokenCipher([old_key])
    encrypted_with_old = old_cipher.encrypt("секрет")

    rotated_cipher = TokenCipher.from_setting(f"{new_key}, {old_key}")
    assert rotated_cipher.decrypt(encrypted_with_old) == "секрет"

    re_encrypted = rotated_cipher.rotate(encrypted_with_old)
    assert TokenCipher([new_key]).decrypt(re_encrypted) == "секрет"


def test_wrong_key_or_damaged_data() -> None:
    encrypted = TokenCipher([generate_key()]).encrypt("секрет")
    other = TokenCipher([generate_key()])

    with pytest.raises(TokenDecryptError):
        other.decrypt(encrypted)
    with pytest.raises(TokenDecryptError):
        other.decrypt("испорчено")
    with pytest.raises(TokenDecryptError):
        other.rotate(encrypted)


@pytest.mark.parametrize("setting", ["", " , ", "не-ключ", "abc,def"])
def test_bad_key_setting(setting: str) -> None:
    with pytest.raises(CryptoConfigError):
        TokenCipher.from_setting(setting)


def test_password_hash_and_verify() -> None:
    stored = hash_password("правильный пароль")

    assert stored.startswith("$argon2id$")
    assert "правильный пароль" not in stored
    assert verify_password(stored, "правильный пароль")
    assert not verify_password(stored, "неправильный пароль")
    assert not needs_rehash(stored)


@pytest.mark.parametrize("password", ["", "1234567", "x" * 129])
def test_weak_passwords_rejected(password: str) -> None:
    with pytest.raises(WeakPasswordError):
        hash_password(password)


def test_broken_hash_is_not_an_error() -> None:
    assert not verify_password("не-хеш", "пароль123")
    assert needs_rehash("не-хеш")
