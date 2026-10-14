"""Печатает новый ключ шифрования для FERNET_KEYS: python -m wbm.security.keygen"""

from wbm.security.crypto import generate_key

if __name__ == "__main__":
    print(generate_key())
