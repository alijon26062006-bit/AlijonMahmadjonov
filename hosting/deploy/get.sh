#!/usr/bin/env bash
# Установка Averix одной командой на чистый сервер Ubuntu 22.04 / 24.04:
#
#   curl -fsSL https://raw.githubusercontent.com/alijon26062006-bit/AlijonMahmadjonov/refs/heads/claude/sharp-dijkstra-2jef38/hosting/deploy/get.sh | sudo bash
#
# Скачивает код панели и запускает установщик, который задаст вопросы (токен Hetzner, домен, email).
# Повторный запуск обновляет панель до последней версии и ничего не спрашивает, если настройки уже есть.
set -euo pipefail

REPO="${AVERIX_REPO:-https://github.com/alijon26062006-bit/AlijonMahmadjonov.git}"
BRANCH="${AVERIX_BRANCH:-claude/sharp-dijkstra-2jef38}"
SRC=/opt/averix-src

if [[ $EUID -ne 0 ]]; then echo "Запустите через sudo: ... | sudo bash"; exit 1; fi

echo "▶ Скачиваю Averix ($BRANCH)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git ca-certificates curl >/dev/null
if [[ -d "$SRC/.git" ]]; then
  git -C "$SRC" fetch -q --depth 1 origin "$BRANCH"
  git -C "$SRC" reset -q --hard FETCH_HEAD
else
  git clone -q --depth 1 --branch "$BRANCH" "$REPO" "$SRC"
fi

exec bash "$SRC/hosting/deploy/install.sh" </dev/tty
