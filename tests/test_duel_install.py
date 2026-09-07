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


@pytest.mark.parametrize("address", ["2.29.11.118", "127.0.0.1", "8.8.8.8", "192.168.1.1"])
def test_ip_address_is_not_a_domain(address):
    """На голый IP сертификат не выдают, а без https Telegram игру не откроет.
    Настоящий сервер как раз на этом и споткнулся."""
    assert not check(f"valid_domain '{address}'")
    assert check(f"looks_like_ip '{address}'")


def test_real_domain_is_not_mistaken_for_an_address():
    assert not check("looks_like_ip 'duel.example.com'")
    assert not check("looks_like_ip 'kanat.duckdns.org'")


def test_free_subdomain_services_work():
    """Своего домена может не быть — бесплатный подойдёт."""
    assert check("valid_domain 'kanat.duckdns.org'")
    assert check("valid_domain 'kanat.ddns.net'")


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


# ── как это запускают ───────────────────────────────────────────────────────


def test_install_command_avoids_process_substitution():
    """`sudo bash <(curl …)` падает с /dev/fd/63: sudo закрывает лишние
    дескрипторы, и подставленный файл исчезает прямо из-под bash. На настоящем
    сервере это уже случилось — пусть больше не вернётся."""
    readme = (ROOT / "README.md").read_text()
    command_lines = [
        line for line in readme.splitlines()
        if "install.sh" in line and "curl" in line and not line.startswith(">")
    ]
    assert command_lines, "в README должна быть команда установки"
    for line in command_lines:
        assert "bash <(" not in line, line
    assert "curl -fsSL -o install-duel.sh" in readme

    # В шапке установщика примеры запуска идут с отступом — проверяем их,
    # а не пояснение, которое как раз про эту ловушку и рассказывает.
    usage = [line for line in INSTALL.read_text().splitlines() if line.startswith("#   ")]
    assert any("curl -fsSL -o install-duel.sh" in line for line in usage)
    assert not any("bash <(" in line for line in usage)


def test_installer_looks_in_other_branches_when_main_has_nothing():
    """Пока код не влит в main, установщик обязан найти его сам."""
    text = INSTALL.read_text()
    assert "DUEL_FALLBACK_BRANCH" in text
    assert "Не нашёл код игры ни в одной ветке" in text


def test_repeat_install_stays_on_the_same_branch():
    """Повторный запуск не должен утащить сервер на main, если ставили с ветки."""
    assert "DUEL_BRANCH_GIVEN" in INSTALL.read_text()


def test_build_check_does_not_depend_on_current_directory():
    """Установщик запускают из любой папки — проверка сборки обязана находить
    игру по абсолютному пути, а не по «.» в sys.path. На сервере это уже
    обернулось ModuleNotFoundError: No module named 'duel'."""
    text = INSTALL.read_text()
    assert 'sys.path.insert(0, ".")' not in text
    assert "PYTHONPATH=" in text


def test_ip_prompt_offers_a_way_out():
    """Ввели IP — надо не просто отказать, а сказать, где взять домен."""
    text = INSTALL.read_text()
    assert "duckdns.org" in text


def test_git_never_runs_without_marking_the_folder_trusted():
    """git с версии 2.35 отказывается работать в папке чужого владельца:
    «detected dubious ownership». На сервере установщик на этом и встал."""
    lines = INSTALL.read_text().splitlines()
    assert any("git_duel()" in line for line in lines), "нужна обёртка над git"
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("git -C") and "safe.directory" not in stripped:
            raise AssertionError(f"git без safe.directory: {stripped}")


def test_update_command_also_marks_the_folder_trusted():
    assert "safe.directory" in CONTROL.read_text()


def test_code_belongs_to_root_and_only_data_to_the_game():
    """Служба не должна иметь права переписать собственный код."""
    text = INSTALL.read_text()
    assert 'chown -R root:root "$DUEL_HOME"' in text
    assert 'chown -R "${DUEL_USER}:${DUEL_USER}" "${DUEL_HOME}/data"' in text
    assert 'chown "${DUEL_USER}:${DUEL_USER}" "$ENV_FILE"' in text


def test_failures_do_not_blame_the_internet_for_everything():
    """«Проверь интернет» на ошибку прав только сбивает с толку."""
    text = INSTALL.read_text()
    assert "Не удалось получить ветку" not in text
    assert "Что сказал git — видно выше" in text


def test_control_command_covers_daily_needs():
    text = CONTROL.read_text()
    for word in ("status", "logs", "restart", "update", "test"):
        assert f"{word})" in text or f"|{word}" in text or f"{word}|" in text
