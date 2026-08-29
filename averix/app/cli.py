"""
Служебные команды.

    python -m app.cli create-admin <логин>
    python -m app.cli migrate
"""
import getpass
import sqlite3
import sys

from .db import connect, migrate
from .security import hash_password


def create_admin(username: str) -> int:
    if len(username) < 3:
        print("Логин должен быть не короче трёх символов.")
        return 1
    password = getpass.getpass("Пароль: ")
    if len(password) < 12:
        print("Пароль должен быть не короче 12 символов.")
        return 1
    if password != getpass.getpass("Повторите: "):
        print("Пароли не совпали.")
        return 1

    migrate()
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO admins (username, password_hash) VALUES (?,?)",
                (username, hash_password(password)),
            )
    except sqlite3.IntegrityError:
        print(f"Администратор «{username}» уже существует.")
        return 1
    print(f"Создан администратор «{username}».")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "migrate":
        applied = migrate()
        print("Применено:", ", ".join(applied) if applied else "нечего применять")
        return 0
    if len(argv) >= 3 and argv[1] == "create-admin":
        return create_admin(argv[2])
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
