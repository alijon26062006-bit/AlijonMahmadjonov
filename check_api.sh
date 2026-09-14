#!/usr/bin/env bash
# Проверка API поставщика. Заказы не создаёт, денег не тратит.
#   bash check_api.sh
#   bash check_api.sh --pubg 5123456789 --ff-cis 123456789 --tg alijon
set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")"
PY="./.venv/bin/python"
[ -x "$PY" ] || PY="python3"
exec "$PY" -m shop.check_api "$@"
