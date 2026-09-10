#!/usr/bin/env bash
# Обновляет наборы cf_ipv4/cf_ipv6 в nftables актуальными официальными диапазонами
# Cloudflare. Атомарно: строим новый набор во временной таблице, проверяем синтаксис,
# заменяем одной командой, SSH не трогаем. При любой ошибке — старые правила остаются.
#
# Запускать по расписанию (раз в сутки, см. cron/systemd timer) и один раз при install.sh.
# Использование: update-cloudflare-firewall.sh [--dry-run]

set -euo pipefail

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

LOG_TAG="[update-cloudflare-firewall]"
V4_URL="https://www.cloudflare.com/ips-v4"
V6_URL="https://www.cloudflare.com/ips-v6"

fail() { echo "${LOG_TAG} ОШИБКА: $1" >&2; exit 1; }

v4_ranges=$(curl -fsS -m 15 "$V4_URL") || fail "не удалось получить $V4_URL"
v6_ranges=$(curl -fsS -m 15 "$V6_URL") || fail "не удалось получить $V6_URL"

# Валидация ответа: это должны быть строки вида a.b.c.d/nn (или IPv6/nn), не пусто,
# не HTML страница ошибки — иначе не применяем вообще.
v4_count=$(echo "$v4_ranges" | grep -cE '^[0-9]{1,3}(\.[0-9]{1,3}){3}/[0-9]{1,2}$' || true)
v6_count=$(echo "$v6_ranges" | grep -cE '^[0-9a-fA-F:]+/[0-9]{1,3}$' || true)

if [[ "$v4_count" -lt 5 || "$v6_count" -lt 1 ]]; then
  fail "ответ Cloudflare выглядит некорректно (v4: $v4_count строк, v6: $v6_count строк) — не применяем"
fi

TMP_CONF=$(mktemp)
trap 'rm -f "$TMP_CONF"' EXIT

{
  echo "table inet hosting_filter {"
  echo "  set cf_ipv4_new { type ipv4_addr; flags interval; elements = { $(echo "$v4_ranges" | paste -sd, -) } }"
  echo "  set cf_ipv6_new { type ipv6_addr; flags interval; elements = { $(echo "$v6_ranges" | paste -sd, -) } }"
  echo "}"
} > "$TMP_CONF"

if ! nft -c -f "$TMP_CONF" 2>/tmp/cf-nft.err; then
  cat /tmp/cf-nft.err >&2
  rm -f /tmp/cf-nft.err
  fail "nft -c (проверка синтаксиса) не прошла — старые правила НЕ тронуты"
fi
rm -f /tmp/cf-nft.err

if [[ $DRY_RUN -eq 1 ]]; then
  echo "${LOG_TAG} dry-run OK: v4=${v4_count} диапазонов, v6=${v6_count} диапазонов"
  exit 0
fi

# Атомарная замена: создаём _new наборы, заполняем, флашим старые, переносим элементы, удаляем _new.
nft -f "$TMP_CONF"
nft flush set inet hosting_filter cf_ipv4
nft flush set inet hosting_filter cf_ipv6
for el in $(echo "$v4_ranges"); do nft add element inet hosting_filter cf_ipv4 "{ $el }"; done
for el in $(echo "$v6_ranges"); do nft add element inet hosting_filter cf_ipv6 "{ $el }"; done
nft delete set inet hosting_filter cf_ipv4_new
nft delete set inet hosting_filter cf_ipv6_new

echo "${LOG_TAG} применено: v4=${v4_count} диапазонов, v6=${v6_count} диапазонов, $(date -u +%FT%TZ)"
logger -t hosting-cloudflare "firewall updated: v4=${v4_count} v6=${v6_count}"
