#!/usr/bin/env bash
# Проверка базы на чистом PostgreSQL: заглушки Supabase → все миграции по порядку → сценарии (e2e/sql/marketplace.sql).
#   DATABASE_URL=postgres://postgres:postgres@127.0.0.1:5432/postgres bash e2e/sql/run.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
ADMIN=${DATABASE_URL:-postgres://postgres:postgres@127.0.0.1:5432/postgres}
DB="${ADMIN%/*}/zud_test"
psql "$ADMIN" -qX -c "drop database if exists zud_test" -c "create database zud_test"
psql "$DB" -qX -v ON_ERROR_STOP=1 -f e2e/sql/stubs.sql 2>&1 | grep -v "wal_level\|HINT" || true
for f in seller/supabase/migrations/*.sql; do PGOPTIONS="-c client_min_messages=warning" psql "$DB" -qX -v ON_ERROR_STOP=1 -f "$f" > /dev/null; done
# -tA: без таблиц, только сообщения проверок; set -o pipefail вернёт ошибку psql, если сценарий упал
for f in marketplace admin; do
  psql "$DB" -qXtA -v ON_ERROR_STOP=1 -f "e2e/sql/$f.sql" 2>&1 | sed -e 's/^psql:[^ ]* NOTICE:  /  /' -e '/^$/d'
done
