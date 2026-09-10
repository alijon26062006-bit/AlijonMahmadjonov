"""Проверка установки без Телеграма:  .venv/bin/python -m counter.selftest

Показывает по пунктам, что готово, а что нет, и что делать.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

GREEN, RED, YELLOW, DIM, OFF = "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[0m"


def ok(text: str) -> bool:
    print(f"  {GREEN}✓{OFF} {text}")
    return True


def fail(text: str, advice: str = "") -> bool:
    print(f"  {RED}✗{OFF} {text}")
    if advice:
        print(f"    {DIM}{advice}{OFF}")
    return False


def warn(text: str, advice: str = "") -> bool:
    print(f"  {YELLOW}!{OFF} {text}")
    if advice:
        print(f"    {DIM}{advice}{OFF}")
    return True


def check_python() -> bool:
    version = "%d.%d.%d" % sys.version_info[:3]
    if sys.version_info < (3, 10):
        return fail(f"Python {version} — старый", "Нужен 3.10 или новее.")
    return ok(f"Python {version}")


def check_libraries() -> bool:
    everything = True
    for module, advice in (
        ("aiogram", "pip install aiogram"),
        ("openpyxl", "pip install openpyxl"),
        ("reportlab", "pip install reportlab"),
    ):
        try:
            __import__(module)
            ok(f"библиотека {module}")
        except ImportError:
            everything = fail(f"нет библиотеки {module}", advice)

    try:
        __import__("vosk")
        ok("библиотека vosk (распознавание речи)")
    except ImportError:
        everything = fail(
            "нет библиотеки vosk",
            "pip install vosk — без неё бот поймёт только числа, написанные цифрами.",
        )

    try:
        __import__("av")
        ok("библиотека av (раскодировать голосовое)")
    except ImportError:
        import shutil

        if shutil.which("ffmpeg"):
            warn("нет библиотеки av, но найден ffmpeg — сойдёт")
        else:
            everything = fail("нечем раскодировать голосовое", "pip install av")
    return everything


def check_font(config) -> bool:
    from . import reports

    if reports.register_fonts(config.font_path, config.font_bold_path):
        return ok(f"шрифт для PDF: {config.font_path}")
    return warn(
        "не найден шрифт с кириллицей",
        "PDF получится латиницей. Лечится: sudo apt install fonts-dejavu-core",
    )


def check_model(config) -> bool:
    from .stt import Recognizer

    recognizer = Recognizer(config.model_path)
    recognizer.load()
    if recognizer.ready:
        return ok(f"голосовая модель загружена: {config.model_path}")
    return fail("голосовая модель не готова", (recognizer.problem or "").replace("\n", " "))


def check_numbers() -> bool:
    from .numbers import SCALE, format_amount, parse_single

    samples = {
        "семь тысяч шестьсот": 7600,
        "семь шестьсот": 7600,
        "пять четыреста": 5400,
        "yetti olti yuz": 7600,
        "7600": 7600,
    }
    everything = True
    for text, expected in samples.items():
        got = parse_single(text)
        if got == expected * SCALE:
            ok(f"«{text}» → {format_amount(got)}")
        else:
            everything = fail(f"«{text}» → {got}, а должно быть {expected}")
    return everything


def check_storage(config) -> bool:
    from . import db

    try:
        with tempfile.TemporaryDirectory() as folder:
            conn = db.connect(Path(folder) / "check.db")
            session = db.current_session(conn, 1)
            worker, _ = db.add_worker(conn, 1, "Проверка")
            db.add_entry(conn, chat_id=1, session_id=session["id"],
                         worker_id=worker["id"], amount=7600 * 100)
            count, total = db.grand_total(conn, 1, session["id"])
            conn.close()
        if (count, total) != (1, 760000):
            return fail("база считает неправильно")
    except Exception as exc:  # noqa: BLE001
        return fail(f"база не работает: {exc}")

    try:
        config.ensure_dirs()
        probe = config.data_dir / ".probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except Exception as exc:  # noqa: BLE001
        return fail(f"не могу писать в {config.data_dir}: {exc}")
    return ok(f"база и папка данных в порядке: {config.data_dir}")


def check_reports(config) -> bool:
    from . import reports
    from .numbers import SCALE

    data = reports.ReportData(
        chat_title="Проверка",
        session_title="Смена",
        period="сейчас",
        unit=config.unit_name,
        rows=[{"name": "Иброхим", "count": 1, "total": 7600 * SCALE}],
        entries=[{"n": 1, "name": "Иброхим", "amount": 7600 * SCALE, "time": "09:00", "note": "семь шестьсот"}],
    )
    everything = True
    try:
        ok(f"Excel собирается ({len(reports.build_xlsx(data))} байт)")
    except Exception as exc:  # noqa: BLE001
        everything = fail(f"Excel не собрался: {exc}")
    try:
        ok(f"PDF собирается ({len(reports.build_pdf(data))} байт)")
    except Exception as exc:  # noqa: BLE001
        everything = fail(f"PDF не собрался: {exc}")
    return everything


def check_token(config) -> bool:
    if config.telegram_token:
        tail = config.telegram_token[-4:]
        return ok(f"токен бота записан (…{tail})")
    return fail(
        "нет токена бота",
        "Возьми у @BotFather и добавь в .env строку COUNTER_BOT_TOKEN=...",
    )


def main() -> int:
    from .config import load_config

    config = load_config(require_token=False)

    print(f"\n\033[1mПроверка счётчика товаров{OFF}\n")
    results = [
        check_python(),
        check_libraries(),
        check_token(config),
        check_storage(config),
        check_font(config),
        check_reports(config),
        check_numbers(),
        check_model(config),
    ]

    print()
    if all(results):
        print(f"{GREEN}Всё готово.{OFF} Запуск:  .venv/bin/python -m counter\n")
        return 0
    print(f"{RED}Есть проблемы — смотри строки с ✗ выше.{OFF}")
    print(f"{DIM}Чаще всего лечится повторным запуском: bash setup-counter.sh{OFF}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
