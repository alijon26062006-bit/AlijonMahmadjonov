#!/usr/bin/env bash
# Прогон всех проверок. Запуск: bash tests/run_all.sh
set -u
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"
status=0
for suite in tests/test_money.py tests/test_texts.py tests/test_wiring.py \
             tests/test_panel.py tests/test_recipient.py \
             tests/test_apifrag.py tests/test_mystars.py tests/test_fazer.py \
             tests/test_wallet.py tests/test_design.py \
             tests/test_reports.py tests/test_dcpay.py \
             tests/test_clients.py tests/test_escape.py tests/test_top.py \
             tests/test_links.py tests/test_promo.py \
             tests/test_flow.py; do
    echo ""
    echo "═══ $suite ═══"
    "$PY" "$suite" || status=1
done
echo ""
[ $status -eq 0 ] && echo "✅ Все проверки пройдены" || echo "❌ Есть провалы"
exit $status
