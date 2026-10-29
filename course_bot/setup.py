"""Мастер установки бота курса: спрашивает токен, узнаёт id владельца, запускает.

Только стандартная библиотека — работает до установки зависимостей.

    python -m course_bot.setup
"""

from __future__ import annotations

import os
import select
import subprocess
import sys
from pathlib import Path

# Общие помощники — из мастера соседнего бота: вывод, чистка вставленного токена, HTTP.
from bot.setup import (
    BOLD, DIM, GREEN, OFF, YELLOW,
    ask, ask_yes, bad, bad_characters, clean_secret, extract_user_id, hint, http_json,
    looks_like_ascii, mask, ok, read_env, say,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ENV_PATH = HERE / ".env"
SERVICE_NAME = "coursebot"
SERVICE_PATH = Path("/etc/systemd/system") / f"{SERVICE_NAME}.service"


def check_token(token: str) -> str | None:
    """@username бота или None, если Телеграм токен не принял."""
    status, body = http_json(f"https://api.telegram.org/bot{token}/getMe")
    if status == 200 and isinstance(body, dict) and body.get("ok"):
        return body["result"].get("username") or ""
    if status in (401, 404):
        bad("Телеграм не принял этот токен.")
        hint("Скопируйте его целиком из сообщения @BotFather — вида 123456789:AAE...")
    elif status == 0:
        bad(f"Нет связи с Телеграмом: {(body or {}).get('error')}")
    else:
        bad(f"Телеграм ответил ошибкой {status}.")
    return None


def ask_token() -> tuple[str, str]:
    say(f"  Откройте в Телеграме {BOLD}@BotFather{OFF} → /newbot (или /mybots → ваш бот → API Token)")
    hint("и скопируйте токен — он вида 123456789:AAE...")
    while True:
        token = clean_secret(ask("Токен бота", secret=True))
        if not token:
            continue
        if not looks_like_ascii(token):
            bad(f"В токене есть русские буквы или лишние символы: {bad_characters(token)}")
            hint("Скопируйте токен ещё раз, не перепечатывая вручную.")
            continue
        username = check_token(token)
        if username is not None:
            ok(f"Токен рабочий — бот @{username}")
            return token, username


def wait_for_start(token: str, username: str) -> int | None:
    """Владелец нажимает «Старт» у своего бота — забираем его id из getUpdates."""
    http_json(f"https://api.telegram.org/bot{token}/deleteWebhook")
    say()
    say(f"  {BOLD}Откройте https://t.me/{username} и нажмите «Старт» (START).{OFF}")
    hint("Так бот узнает, что вы — его владелец и администратор.")
    hint("Если не получается — нажмите Enter и впишите свой id вручную.")
    say(f"\n  {DIM}Жду, пока вы нажмёте «Старт»…{OFF}")
    for _ in range(36):  # около трёх минут
        if select.select([sys.stdin], [], [], 0)[0]:
            sys.stdin.readline()
            return None
        status, body = http_json(
            f"https://api.telegram.org/bot{token}/getUpdates?timeout=5&offset=-1", timeout=15)
        if status == 200 and isinstance(body, dict):
            found = extract_user_id(body)
            if found:
                user_id, name = found
                ok(f"Владелец бота: {name}, id {user_id}")
                return user_id
    bad("Не дождался нажатия «Старт».")
    return None


def ask_owner_id() -> str:
    hint("Свой id можно узнать у @userinfobot — это число.")
    while True:
        value = ask("Ваш id в Телеграме").replace(" ", "")
        if value.isdigit():
            return value
        bad("Нужно число, например 123456789.")


def render_env(token: str, admin_ids: str) -> str:
    return (
        "# Создано мастером установки: python -m course_bot.setup\n"
        "# Никому не показывайте этот файл — здесь токен бота.\n\n"
        f"BOT_TOKEN={token}\n"
        f"ADMIN_IDS={admin_ids}\n"
    )


def write_env(token: str, admin_ids: str, path: Path = ENV_PATH) -> None:
    path.write_text(render_env(token, admin_ids), encoding="utf-8")
    path.chmod(0o600)


# ── автозапуск ─────────────────────────────────────────────────────────────

def render_service(python: Path, workdir: Path, user: str) -> str:
    return f"""[Unit]
Description=Telegram bot for the course "Python s nulya"
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={user}
WorkingDirectory={workdir}
ExecStart={python} -m course_bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""


def can_install_service() -> bool:
    import shutil

    return os.geteuid() == 0 and shutil.which("systemctl") is not None


def install_service() -> bool:
    # Бот работает от имени владельца папки с кодом: при «curl | sudo bash» код лежит
    # в /root, и запуск от SUDO_USER упал бы без прав на чтение.
    user = ROOT.owner()
    SERVICE_PATH.write_text(render_service(Path(sys.executable), ROOT, user), encoding="utf-8")
    try:
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "enable", SERVICE_NAME], check=True, capture_output=True)
        subprocess.run(["systemctl", "restart", SERVICE_NAME], check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        bad(f"systemd не смог запустить бота: {exc}")
        return False
    return True


def finish(username: str) -> int:
    if can_install_service() and install_service():
        say(f"\n{GREEN}{BOLD}Готово! Бот работает круглые сутки и сам включится после перезагрузки.{OFF}")
        say(f"Откройте https://t.me/{username} — у вас в меню есть «⚙️ Админ-панель».")
        say("Там укажите цену, реквизиты и подключите канал.\n")
        hint(f"Состояние:  systemctl status {SERVICE_NAME}")
        hint(f"Логи:       journalctl -u {SERVICE_NAME} -f")
        hint(f"Перезапуск: systemctl restart {SERVICE_NAME}")
        return 0

    say(f"\n{YELLOW}⚠ Автозапуск не настроен{OFF} {DIM}(нужен root и systemd){OFF}")
    hint("Бот будет работать, только пока открыт этот терминал.")
    say(f"\n{GREEN}{BOLD}Запускаю бота.{OFF} {DIM}Остановить — Ctrl+C{OFF}\n")
    from .main import main as run_bot

    return run_bot()


def main() -> int:
    say(f"\n{BOLD}Настройка бота курса «Python с нуля»{OFF}")

    existing = read_env(ENV_PATH)
    if existing.get("BOT_TOKEN") and existing.get("ADMIN_IDS"):
        ok(f"Настройки уже есть: токен {mask(existing['BOT_TOKEN'])}, владелец {existing['ADMIN_IDS']}")
        if not ask_yes("Ввести токен заново?", default=False):
            username = check_token(existing["BOT_TOKEN"])
            return finish(username or "ваш_бот")

    say(f"\n{BOLD}[1/2] Токен бота{OFF}")
    token, username = ask_token()

    say(f"\n{BOLD}[2/2] Владелец бота{OFF}")
    owner = wait_for_start(token, username)
    admin_ids = str(owner) if owner else ask_owner_id()

    write_env(token, admin_ids)
    ok(f"Настройки записаны: {ENV_PATH} (доступ только вам)")
    return finish(username)


if __name__ == "__main__":
    raise SystemExit(main())
