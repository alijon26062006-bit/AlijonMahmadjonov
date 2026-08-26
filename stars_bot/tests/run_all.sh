#!/usr/bin/env bash
# Прогон всех проверок. Запуск: bash tests/run_all.sh
set -u
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"
status=0
for suite in tests/test_money.py tests/test_texts.py tests/test_wiring.py tests/test_flow.py; do
    echo ""
    echo "═══ $suite ═══"
    "$PY" "$suite" || status=1
done
echo ""
[ $status -eq 0 ] && echo "✅ Все проверки пройдены" || echo "❌ Есть провалы"
exit $status
