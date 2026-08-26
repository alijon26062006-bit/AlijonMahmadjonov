"""Мастер первой настройки: создаёт .env, ничего не спрашивая дважды.

Запуск:  python setup.py
Работает на голом Python, ставить ничего не нужно.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
ENV = BASE / ".env"
EXAMPLE = BASE / ".env.example"

TOKEN_RE = re.compile(r"^\d{6,}:[A-Za-z0-9_-]{30,}$")


def _open_input():
    """Ввод с терминала. Если stdin занят (скрипт пришёл по конвейеру
    из curl), читаем напрямую из /dev/tty."""
    if sys.stdin is not None and sys.stdin.isatty():
        return None
    try:
        return open("/dev/tty", encoding="utf-8")
    except OSError:
        return None


_TTY = _open_input()


def _read(prompt: str) -> str:
    if _TTY is None:
        return input(prompt)
    print(prompt, end="", flush=True)
    line = _TTY.readline()
    if not line:
        raise EOFError
    return line


def ask(prompt: str, *, current: str = "", validate=None, allow_empty: bool = False) -> str:
    """Спросить значение. Enter — оставить текущее."""
    while True:
        hint = f" [{current}]" if current else ""
        answer = _read(f"{prompt}{hint}: ").strip()
        if not answer:
            if current:
                return current
            if allow_empty:
                return ""
            print("  ⚠️  Это поле обязательно.")
            continue
        if validate:
            problem = validate(answer)
            if problem:
                print(f"  ⚠️  {problem}")
                continue
        return answer


def check_token(value: str) -> str | None:
    if not TOKEN_RE.match(value):
        return "Токен выглядит неправильно. Формат: 123456789:AAH..."
    return None


def check_id(value: str) -> str | None:
    parts = [p.strip() for p in value.replace(";", ",").split(",") if p.strip()]
    if not parts or not all(p.isdigit() for p in parts):
        return "ID — это только цифры. Несколько админов — через запятую."
    return None


def check_seed(value: str) -> str | None:
    words = value.split()
    if len(words) != 24:
        return f"Нужно ровно 24 слова, а получено {len(words)}."
    if not all(word.isalpha() for word in words):
        return "Сид-фраза состоит только из слов латиницей, без цифр и знаков."
    return None


def check_price(value: str) -> str | None:
    try:
        if float(value.replace(",", ".")) <= 0:
            return "Цена должна быть больше нуля."
    except ValueError:
        return "Введите число, например 0.25"
    return None


def to_diram(value: str) -> int:
    return round(float(value.replace(",", ".")) * 100)


def read_existing() -> dict[str, str]:
    if not ENV.exists():
        return {}
    values = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.split("  #")[0].strip()
    return values


def write_env(values: dict[str, str]) -> None:
    """Пишем поверх .env.example, сохраняя комментарии."""
    lines = []
    for line in EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in values:
                lines.append(f"{key}={values[key]}")
                continue
        lines.append(line)
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if not EXAMPLE.exists():
        print("❌ Не найден .env.example — запускайте скрипт из папки stars_bot.")
        sys.exit(1)

    print("=" * 58)
    print("  Настройка бота. Enter — оставить значение в скобках.")
    print("=" * 58)

    old = read_existing()
    new = dict(old)

    print("\n── Telegram ──")
    print("Токен берётся у @BotFather, ID — у @userinfobot.")
    new["BOT_TOKEN"] = ask("Токен бота", current=old.get("BOT_TOKEN", ""), validate=check_token)
    new["ADMIN_IDS"] = ask("Твой Telegram ID", current=old.get("ADMIN_IDS", ""), validate=check_id)

    print("\n── Реквизиты для приёма переводов ──")
    new["PAY_CARD_NUMBER"] = ask("Номер карты", current=old.get("PAY_CARD_NUMBER", ""))
    new["PAY_CARD_HOLDER"] = ask("Имя владельца", current=old.get("PAY_CARD_HOLDER", ""))
    new["PAY_CARD_BANK"] = ask("Банк", current=old.get("PAY_CARD_BANK", ""))
    new["PAY_CITY"] = ask("Город", current=old.get("PAY_CITY", "") or "Душанбе")

    print("\n── Цены ──")
    current_price = old.get("STAR_PRICE_DIRAM", "")
    shown = f"{int(current_price) / 100:.2f}" if current_price.isdigit() else ""
    price = ask("Цена одной звезды в сомони (напр. 0.25)",
                current=shown, validate=check_price)
    new["STAR_PRICE_DIRAM"] = str(to_diram(price))

    current_min = old.get("MIN_DEPOSIT_DIRAM", "")
    shown_min = f"{int(current_min) / 100:.2f}" if current_min.isdigit() else "10"
    minimum = ask("Минимальное пополнение в сомони",
                  current=shown_min, validate=check_price)
    new["MIN_DEPOSIT_DIRAM"] = str(to_diram(minimum))

    print("\n── Как выдавать звёзды ──")
    print("mock    — бот работает, но ничего не отправляет (для проверки).")
    print("mystars — api.mystars.tg. Сид-фразу НЕ спрашивает: счёт на оплату")
    print("          приходит вам в Telegram, платите в один тап Tonkeeper.")
    print("api     — apifragment.online. Работает без вашего участия, но")
    print("          хранит вашу сид-фразу у себя.")
    mode = ask("Режим (mock/mystars/api)",
               current=old.get("FRAGMENT_MODE", "") or "mock",
               validate=lambda v: None if v in ("mock", "mystars", "api")
               else "Только mock, mystars или api")
    new["FRAGMENT_MODE"] = mode

    if mode == "mystars":
        print()
        print("  Ключ выдают в @my_stars_tg_bot — раздел «API access».")
        print()
        new["MYSTARS_API_KEY"] = ask("Ключ MyStars (X-Api-Key)",
                                     current=old.get("MYSTARS_API_KEY", ""))
        new["MYSTARS_CURRENCY"] = ask(
            "Чем платить (ton / usdt_ton)",
            current=old.get("MYSTARS_CURRENCY", "") or "ton",
            validate=lambda v: None if v in ("ton", "usdt_ton") else "Только ton или usdt_ton",
        )

    if mode == "api":
        print()
        print("  " + "!" * 54)
        print("  ВАЖНО ПРО СИД-ФРАЗУ")
        print()
        print("  Сервис требует 24 слова вашего TON-кошелька и хранит их")
        print("  у себя, чтобы входить на Fragment от вашего имени.")
        print("  Это значит: владельцы сервиса технически могут вывести")
        print("  все деньги с этого кошелька в любой момент.")
        print()
        print("  Заведите ОТДЕЛЬНЫЙ кошелёк только для бота и держите на нём")
        print("  оборотную сумму на пару дней, а не все сбережения.")
        print("  " + "!" * 54)
        print()
        new["FRAGMENT_API_KEY"] = ask("API-токен ApiFragment",
                                      current=old.get("FRAGMENT_API_KEY", ""))
        new["FRAGMENT_WALLET_SEED"] = ask(
            "Сид-фраза кошелька (24 слова через пробел)",
            current=old.get("FRAGMENT_WALLET_SEED", ""),
            validate=check_seed,
        )
        new["FRAGMENT_PAYMENT_METHOD"] = ask(
            "Чем платить на Fragment (ton / usdt_ton)",
            current=old.get("FRAGMENT_PAYMENT_METHOD", "") or "ton",
            validate=lambda v: None if v in ("ton", "usdt_ton") else "Только ton или usdt_ton",
        )

    print("\n── Необязательное ──")
    new["SUPPORT_USERNAME"] = ask("Юзернейм поддержки без @",
                                  current=old.get("SUPPORT_USERNAME", ""), allow_empty=True)
    new["REVIEWS_URL"] = ask("Ссылка на канал с отзывами",
                             current=old.get("REVIEWS_URL", ""), allow_empty=True)

    write_env(new)

    print("\n" + "=" * 58)
    print(f"  ✅ Настройки сохранены в {ENV}")
    print("=" * 58)
    print("\nЗапуск бота:\n    python -m app.main\n")
    if mode == "mock":
        print("Сейчас режим mock — звёзды НЕ отправляются.")
        print("Проверьте бота, потом запустите setup.py снова и включите api.\n")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nОтменено.")
