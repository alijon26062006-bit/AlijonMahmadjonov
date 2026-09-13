#!/usr/bin/env bash
# Removes every account and everything people made, and keeps the platform.
#
# For a launch: you tested with your own registrations and now want the site to
# start from nothing, without reinstalling it. Afterwards you sign up again the
# ordinary way and make yourself an administrator again.
#
#   ./scripts/reset-users.sh            # says what it would delete and stops
#   ./scripts/reset-users.sh --yes      # does it, after taking a backup
#
# What survives: the catalogue of professions and skills, платформенные
# настройки, feature flags, комиссия, веса подбора, список платёжных
# провайдеров and the migration history. What goes: accounts, profiles,
# projects, proposals, contracts, payments, messages, reviews, portfolios,
# services, notifications, moderation, аудит and every uploaded file —
# including identity documents, which is the point of doing this properly
# rather than deleting rows by hand.
#
# It takes a full backup first. If you delete the wrong thing, restore it:
#   ./scripts/restore.sh /var/backups/averix/averix-db-<stamp>.dump

set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.production.yml}"
COMPOSE=(docker compose -f "$COMPOSE_FILE")
[ -f docker-compose.nginx.yml ] && [ -n "${AVERIX_WEB_HOST_PORT:-}" ] && COMPOSE+=(-f docker-compose.nginx.yml)

# The database's name and user live in .env, not in the shell that runs this.
# Reading them here is what keeps the script from politely emptying a database
# called "averix" that does not exist while the real one keeps every account.
if [ -f .env ]; then
  POSTGRES_USER="$(sed -n 's/^POSTGRES_USER=//p' .env | tail -1)"
  POSTGRES_DB="$(sed -n 's/^POSTGRES_DB=//p' .env | tail -1)"
fi
PG_USER="${POSTGRES_USER:-averix}"
PG_DB="${POSTGRES_DB:-averix}"

# Prove the database is there and is the one with the accounts, before the
# backup and long before the delete.
if ! "${COMPOSE[@]}" exec -T postgres psql -U "$PG_USER" -d "$PG_DB" -c 'SELECT 1' > /dev/null 2>&1; then
  echo "Не получилось открыть базу «$PG_DB» пользователем «$PG_USER»." >&2
  echo "Проверьте, что стек запущен, и что POSTGRES_USER и POSTGRES_DB в .env те же:" >&2
  echo "  ${COMPOSE[*]} ps" >&2
  exit 1
fi

psql_run() { "${COMPOSE[@]}" exec -T postgres psql -U "$PG_USER" -d "$PG_DB" -v ON_ERROR_STOP=1 "$@"; }

# The tables holding what people made. Everything absent from this list is
# reference data the product needs to work at all — deleting it would leave a
# site with no professions to choose from.
TABLES="
users user_roles sessions auth_tokens oauth_states push_subscriptions user_languages
client_profiles developer_profiles developer_skills developer_specialisations developer_photos
identity_verifications identity_documents identity_review_actions admin_access_logs
admin_permission_grants admin_actions audit_logs
projects project_skills project_specialisations project_attachments project_invitations
project_views project_features match_scores assistant_sessions
proposals proposal_milestones proposal_portfolio_links
contracts contract_participants milestones milestone_events deliverables
disputes dispute_messages
payment_intents payment_transactions payment_webhook_events ledger_entries
conversations conversation_participants messages message_attachments message_receipts
reviews completed_project_history completed_project_skills
portfolio_projects portfolio_images portfolio_links portfolio_skills
services service_tiers service_skills service_portfolio_links
saved_developers saved_projects
notifications notification_deliveries notification_preferences email_log
moderation_queue reports
github_accounts github_analysis github_repositories github_repository_languages
github_detected_technologies
files jobs rate_limit_events
"

LIST="$(echo "$TABLES" | tr -s '[:space:]' ' ' | sed 's/^ //; s/ $//' | sed 's/ /, /g')"
# The same list as SQL literals, for the check that nothing outside it points
# at users through a column that cannot be emptied.
QUOTED="$(echo "$TABLES" | tr -s '[:space:]' '\n' | grep -v '^$' | sed "s/.*/'&'/" | paste -sd, -)"

echo "Сейчас в базе:"
psql_run -At -c "
  SELECT '  пользователей: ' || (SELECT count(*) FROM users)
      || E'\n  заказов: '     || (SELECT count(*) FROM projects)
      || E'\n  сделок: '      || (SELECT count(*) FROM contracts)
      || E'\n  услуг: '       || (SELECT count(*) FROM services)
      || E'\n  заявок на проверку личности: ' || (SELECT count(*) FROM identity_verifications)"

if [ "${1:-}" != "--yes" ]; then
  echo
  echo "Это удалит все аккаунты и всё, что люди сделали, без возможности отменить."
  echo "Останутся профессии, навыки, настройки площадки и история миграций."
  echo
  echo "Если вы уверены:"
  echo "  ./scripts/reset-users.sh --yes"
  exit 1
fi

echo
echo "Сначала резервная копия — на случай, если это была не та база."
./scripts/backup.sh

echo
echo "Очистка..."
# Deliberately not TRUNCATE ... CASCADE.
#
# Four tables the platform needs — настройки, feature flags, комиссия и веса
# подбора — carry a "кто менял" column pointing at users, and CASCADE takes
# that as permission to empty them too. That would delete the commission rate
# and the transfer details along with the test accounts, and the operator would
# find out when the first real payment failed. TRUNCATE without CASCADE simply
# refuses while those references exist.
#
# So: those columns are set to NULL first (who changed a setting is worth less
# than the setting), foreign-key triggers are switched off for this one session,
# and the rows are deleted in any order without tripping over ON DELETE
# RESTRICT. One transaction: either the site is empty afterwards or nothing
# changed at all.
psql_run <<SQL
BEGIN;

DO \$\$
DECLARE ref record;
BEGIN
  FOR ref IN
    SELECT c.conrelid::regclass AS tbl, a.attname AS col, a.attnotnull AS required
    FROM pg_constraint c
    JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
    WHERE c.confrelid = 'users'::regclass AND c.contype = 'f'
      AND c.conrelid <> ALL (ARRAY[$QUOTED]::regclass[])
  LOOP
    -- A table outside the list that *requires* a user would be left with rows
    -- pointing at nobody. Stop instead of guessing: the list needs updating.
    IF ref.required THEN
      RAISE EXCEPTION 'таблица % ссылается на users через обязательный столбец % — добавьте её в список очистки', ref.tbl, ref.col;
    END IF;
    EXECUTE format('UPDATE %s SET %I = NULL WHERE %I IS NOT NULL', ref.tbl, ref.col, ref.col);
  END LOOP;
END
\$\$;

SET LOCAL session_replication_role = replica;

DO \$\$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[$QUOTED] LOOP
    EXECUTE format('DELETE FROM %I', t);
  END LOOP;
END
\$\$;

-- Счётчики тоже с начала: следующая запись в журнале — первая, а не 4913-я.
DO \$\$
DECLARE s record;
BEGIN
  FOR s IN
    SELECT DISTINCT pg_get_serial_sequence(t, a.attname) AS seq
    FROM unnest(ARRAY[$QUOTED]) AS t
    JOIN pg_attribute a ON a.attrelid = t::regclass AND a.attnum > 0 AND NOT a.attisdropped
    WHERE pg_get_serial_sequence(t, a.attname) IS NOT NULL
  LOOP
    EXECUTE format('ALTER SEQUENCE %s RESTART', s.seq);
  END LOOP;
END
\$\$;

COMMIT;
SQL

# The uploads go with the rows that named them — otherwise the disk keeps
# every avatar and every passport photograph of people who no longer exist.
if "${COMPOSE[@]}" exec -T api test -d /data/storage 2>/dev/null; then
  "${COMPOSE[@]}" exec -T api sh -c 'rm -rf /data/storage/private/* /data/storage/public/* 2>/dev/null; true'
  echo "  файлы удалены (включая снимки документов)"
else
  echo "  файлы лежат в S3 — удалите содержимое бакетов у провайдера отдельно"
fi

echo
LEFT="$(psql_run -At -c 'SELECT count(*) FROM users' | tr -d '[:space:]')"
if [ "$LEFT" != "0" ]; then
  echo "  ВНИМАНИЕ: пользователей осталось $LEFT — очистка не прошла полностью." >&2
  echo "  Резервная копия на месте; ничего не предпринимайте до выяснения." >&2
  exit 1
fi
echo "  пользователей осталось: 0 — все адреса свободны для регистрации заново"
psql_run -At -c "SELECT '  профессий в справочнике: ' || count(*) FROM specialisations"
echo
echo "Готово. Теперь зарегистрируйтесь на сайте заново, а потом:"
echo "  ${COMPOSE[*]} exec api averixctl create-admin --email вы@example.com"
