"""Проверка ключей перед запуском: python -m reviziya_server.check

Печатает по строке на каждый ключ и выходит с кодом:
0 всё работает, 1 токен бота не подошёл, 2 ключ Anthropic не подошёл, 3 оба, 4 нет связи.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

import anthropic

from .config import load_config


def check_bot(token: str) -> tuple[str, str]:
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getMe", timeout=15) as response:
            return "ok", json.load(response)["result"]["username"]
    except urllib.error.HTTPError as exc:
        return ("bad", "") if exc.code in (401, 404) else ("unknown", f"Telegram ответил {exc.code}")
    except Exception as exc:  # нет сети, DNS, таймаут
        return "unknown", str(exc)


def check_key(api_key: str, model: str) -> tuple[str, str]:
    try:
        anthropic.Anthropic(api_key=api_key, max_retries=1, timeout=20.0).models.retrieve(model)
        return "ok", model
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
        return "bad", ""
    except anthropic.NotFoundError:
        return "ok", f"ключ рабочий, но модели {model} у него нет"
    except Exception as exc:
        return "unknown", str(exc)


def main() -> int:
    config = load_config()
    bot, bot_detail = check_bot(config.bot_token)
    key, key_detail = check_key(config.anthropic_api_key, config.model)
    print(f"BOT {bot} {bot_detail}")
    print(f"KEY {key} {key_detail}")
    code = (1 if bot == "bad" else 0) + (2 if key == "bad" else 0)
    if code == 0 and "unknown" in (bot, key):
        return 4
    return code


if __name__ == "__main__":
    sys.exit(main())
