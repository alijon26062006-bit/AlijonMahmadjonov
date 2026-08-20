"""Статическая проверка кода.

NameError вроде «name 'message' is not defined» не ловится ни синтаксисом, ни
обычными тестами — только запуском той самой ветки. pyflakes находит такое
за секунду, поэтому проверка стоит прямо в тестах.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ["bot.py", "config.py", "core", "handlers", "services", "storage"]


def test_no_undefined_names_or_dead_imports():
    result = subprocess.run(
        [sys.executable, "-m", "pyflakes", *PACKAGES],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    problems = [line for line in result.stdout.splitlines() if line.strip()]
    assert not problems, "pyflakes нашёл проблемы:\n" + "\n".join(problems)


def test_every_module_imports_cleanly():
    """Модуль, который не импортируется, уронит бота при запуске."""
    import importlib

    modules = [
        path.relative_to(ROOT).with_suffix("").as_posix().replace("/", ".")
        for package in PACKAGES
        for path in ([ROOT / package] if package.endswith(".py") else (ROOT / package).rglob("*.py"))
        if path.name != "__init__.py"
    ]
    for name in modules:
        if name == "bot":
            continue  # точка входа требует настроенного окружения
        importlib.import_module(name)
