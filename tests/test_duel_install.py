"""Установщик: проверки значений и то, что он пишет в файлы.

Саму установку тут не запускаем — она трогает systemd и nginx. Зато всё, что
решает установщик до этого, проверяется: без этого одна опечатка в домене
превращается в непонятную ошибку certbot посреди установки.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "deploy" / "install.sh"
CONTROL = ROOT / "deploy" / "duel"
SERVICE = ROOT / "deploy" / "duel.service"


def call(snippet: str, **env) -> subprocess.CompletedProcess:
    """Подключает установщик и вызывает из него одну функцию."""
    prefix = "".join(f"export {k}={v}; " for k, v in env.items())
    script = f'{prefix}source "{INSTALL}" >/dev/null 2>&1; {snippet}'
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True)


def check(snippet: str) -> bool:
    return call(f"{snippet} && echo ДА || echo НЕТ").stdout.strip() == "ДА"


# ── синтаксис ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("script", [INSTALL, CONTROL])
def test_scripts_are_valid_bash(script):
    assert subprocess.run(["bash", "-n", str(script)]).returncode == 0


@pytest.mark.parametrize("script", [INSTALL, CONTROL])
def test_scripts_pass_shellcheck(script):
    if shutil.which("shellcheck") is None:
        pytest.skip("shellcheck не установлен")
    done = subprocess.run(
        ["shellcheck", "-S", "warning", str(script)], capture_output=True, text=True
    )
    assert done.returncode == 0, done.stdout


def test_sourcing_does_not_install_anything():
    """Установщик можно подключить и не получить установку: на этом стоят тесты."""
    done = call("echo подключено")
    assert done.stdout.strip() == "подключено"
    assert "Математическая дуэль" not in done.stdout


# ── токен ───────────────────────────────────────────────────────────────────


def test_real_looking_token_passes():
    assert check("valid_token '7123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw'")


@pytest.mark.parametrize(
    "junk",
    [
        "",
        "просто текст",
        "123:abc",                      # слишком короткая вторая часть
        "abc:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw",  # номер бота не число
        "7123456789 AAHdqTcvCH1vGWJxfSeofSAs0K5",  # пробел вместо двоеточия
        "7123456789:AAHdqTcvCH1vGWJxfSeof SAs0K5PALD",  # пробел внутри
    ],
)
def test_junk_token_is_rejected(junk):
    assert not check(f"valid_token '{junk}'")


# ── домен ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("domain", ["duel.example.com", "igra.tj", "a-b.c-d.info"])
def test_good_domain_passes(domain):
    assert check(f"valid_domain '{domain}'")


@pytest.mark.parametrize(
    "junk",
    [
        "",
        "localhost",                      # без точки сертификат не выпустить
        "https://duel.example.com",       # адрес целиком, а не домен
        "duel.example.com/игра",
        "-duel.example.com",
        "duel..com",
        "дуэль.рф",                       # кириллицу нужно вводить в punycode
    ],
)
def test_junk_domain_is_rejected(junk):
    assert not check(f"valid_domain '{junk}'")


def test_absurdly_long_domain_is_rejected():
    assert not check(f"valid_domain '{'a' * 250}.com'")


# ── почта ───────────────────────────────────────────────────────────────────


def test_email_checks():
    assert check("valid_email 'alijon@example.com'")
    assert not check("valid_email 'alijon'")
    assert not check("valid_email 'alijon@example'")


# ── что попадает в файлы ────────────────────────────────────────────────────


def test_env_file_has_everything_the_game_needs():
    out = call("render_env 'СЕКРЕТ' 'duel.example.com'").stdout
    assert "DUEL_BOT_TOKEN=СЕКРЕТ" in out
    assert "DUEL_PUBLIC_URL=https://duel.example.com" in out
    assert "DUEL_HOST=127.0.0.1" in out
    assert "DUEL_DEV_MODE=0" in out, "на боевом сервере подпись Telegram обязана проверяться"


def test_env_file_keeps_the_port_it_was_given():
    out = call("render_env 'x' 'y.ru'", DUEL_PORT="9099").stdout
    assert "DUEL_PORT=9099" in out


def test_nginx_config_lets_the_websocket_through():
    out = call("render_nginx 'duel.example.com'").stdout
    assert "server_name duel.example.com;" in out
    assert "location /ws" in out
    assert 'proxy_set_header Upgrade $http_upgrade;' in out
    assert 'proxy_set_header Connection "upgrade";' in out
    assert "proxy_http_version 1.1;" in out


def test_nginx_does_not_cut_a_long_match():
    """Час на соединение: матч «до победы» не должен обрываться посреди игры."""
    out = call("render_nginx 'duel.example.com'").stdout
    assert "proxy_read_timeout 3600s;" in out
    assert "proxy_send_timeout 3600s;" in out


def test_nginx_config_is_http_only_at_first():
    """Сертификата ещё нет: упомяни его здесь — и nginx не запустится."""
    out = call("render_nginx 'duel.example.com'").stdout
    assert "ssl_certificate" not in out
    assert "listen 80;" in out


def test_nginx_points_at_the_port_from_settings():
    out = call("render_nginx 'duel.example.com'", DUEL_PORT="9099").stdout
    assert "http://127.0.0.1:9099" in out


# ── служба ──────────────────────────────────────────────────────────────────


def test_service_restarts_the_game_and_survives_reboot():
    unit = SERVICE.read_text()
    assert "ExecStart=/opt/duel/.venv/bin/python -m duel.main" in unit
    assert "Restart=always" in unit
    assert "WantedBy=multi-user.target" in unit


def test_service_can_write_only_to_its_own_data():
    unit = SERVICE.read_text()
    assert "ProtectSystem=strict" in unit
    assert "ReadWritePaths=/opt/duel/data" in unit
    assert "NoNewPrivileges=true" in unit


def test_control_command_covers_daily_needs():
    text = CONTROL.read_text()
    for word in ("status", "logs", "restart", "update", "test"):
        assert f"{word})" in text or f"|{word}" in text or f"{word}|" in text
