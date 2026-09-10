#!/usr/bin/env bash
# Периодическая проверка здоровья сервера + злоупотреблений по клиентам.
# Запускается через systemd timer каждые 5 минут (systemd/hosting-monitor.timer).
# При превышении порогов шлёт алерт в Telegram (scripts/telegram-alert.sh).
#
# Пороги — см. спецификацию (раздел ALERTS). "Sustained N минут" здесь
# приближённо реализовано через двухкратное подтверждение: если порог превышен
# и в прошлый прогон (5 минут назад) тоже был превышен — тревога уходит, иначе
# только запоминается (см. STATE_DIR/monitor-flags/*).

set -uo pipefail  # без -e: одна неудачная проверка не должна прерывать остальные

HOSTING_ROOT="${HOSTING_ROOT:-/opt/hosting}"
STATE_DIR="${STATE_DIR:-${HOSTING_ROOT}/var}/monitor-flags"
PHP_BIN="${PHP_BIN:-php}"
HELPER="${HOSTING_ROOT}/hosting/panel/bin/monitor-helper.php"
ALERT="${HOSTING_ROOT}/hosting/scripts/telegram-alert.sh"
mkdir -p "$STATE_DIR"

alert() {
  echo "[monitor] АЛЕРТ: $1"
  bash "$ALERT" "🔴 $1"
}

# Срабатывает только если флаг уже стоял с прошлого прогона — иначе просто ставит флаг.
sustained() {
  local key="$1" message="$2"
  local flag="${STATE_DIR}/${key}"
  if [[ -f "$flag" ]]; then
    alert "$message"
  else
    touch "$flag"
  fi
}

clear_flag() {
  rm -f "${STATE_DIR}/${1}"
}

echo "=== monitor.sh $(date -u +%FT%TZ) ==="

# ── память ───────────────────────────────────────────────────────────────
if command -v free >/dev/null 2>&1; then
  read -r _ total used free_ shared buffcache avail < <(free -m | awk '/^Mem:/')
  percent=$(( used * 100 / total ))
  echo "RAM: ${used}/${total} МБ (${percent}%)"
  if [[ $percent -ge 90 ]]; then sustained "ram" "RAM использована на ${percent}% (${used}/${total} МБ)"; else clear_flag ram; fi
fi

# ── диск и inode ─────────────────────────────────────────────────────────
DATA_MOUNT="${HOSTING_USERS_ROOT:-/home/hosting}"
if [[ -d "$DATA_MOUNT" ]]; then
  disk_percent=$(df -P "$DATA_MOUNT" | awk 'NR==2{gsub("%","",$5); print $5}')
  inode_percent=$(df -iP "$DATA_MOUNT" | awk 'NR==2{gsub("%","",$5); print $5}')
  echo "Диск: ${disk_percent}%, inode: ${inode_percent}%"
  [[ "${disk_percent:-0}" -ge 80 ]] && alert "Диск заполнен на ${disk_percent}% (${DATA_MOUNT})"
  [[ "${inode_percent:-0}" -ge 80 ]] && alert "Inode заполнены на ${inode_percent}% (${DATA_MOUNT})"
fi

# ── load average / iowait ───────────────────────────────────────────────
if [[ -r /proc/loadavg ]]; then
  load1=$(awk '{print $1}' /proc/loadavg)
  cores=$(nproc 2>/dev/null || echo 1)
  echo "Load: ${load1} (ядер: ${cores})"
fi
if command -v mpstat >/dev/null 2>&1; then
  iowait=$(mpstat 1 1 2>/dev/null | awk '/Average/{print $(NF-2)}')
  if [[ -n "$iowait" ]]; then
    echo "iowait: ${iowait}%"
    iowait_int=${iowait%.*}
    if [[ "${iowait_int:-0}" -ge 10 ]]; then sustained "iowait" "iowait держится на ${iowait}% — диск не успевает"; else clear_flag iowait; fi
  fi
fi

# ── MariaDB ──────────────────────────────────────────────────────────────
if command -v mysqladmin >/dev/null 2>&1 && mysqladmin ping --connect-timeout=3 >/dev/null 2>&1; then
  conns=$(mysqladmin status 2>/dev/null | grep -oE 'Threads: [0-9]+' | awk '{print $2}')
  maxconns=$(mysql -N -e "SHOW VARIABLES LIKE 'max_connections'" 2>/dev/null | awk '{print $2}')
  slow=$(mysql -N -e "SHOW GLOBAL STATUS LIKE 'Slow_queries'" 2>/dev/null | awk '{print $2}')
  if [[ -n "$conns" && -n "$maxconns" && "$maxconns" -gt 0 ]]; then
    conn_percent=$(( conns * 100 / maxconns ))
    echo "MariaDB: ${conns}/${maxconns} соединений (${conn_percent}%), slow queries: ${slow:-?}"
    [[ $conn_percent -ge 80 ]] && alert "MariaDB: занято ${conn_percent}% соединений (${conns}/${maxconns})"
  fi
else
  echo "MariaDB: недоступна для проверки (mysqladmin ping не прошёл)"
  alert "MariaDB недоступна — mysqladmin ping не отвечает"
fi

# ── упавшие systemd-юниты ───────────────────────────────────────────────
if command -v systemctl >/dev/null 2>&1; then
  failed=$(systemctl --failed --no-legend 2>/dev/null | wc -l)
  echo "Упавшие systemd-юниты: ${failed}"
  [[ "${failed:-0}" -gt 0 ]] && alert "$(systemctl --failed --no-legend | awk '{print $1}' | tr '\n' ' ') — упавшие systemd-юниты"
fi

# ── очередь воркера ──────────────────────────────────────────────────────
if [[ -x "$HELPER" ]]; then
  pending=$("$PHP_BIN" "$HELPER" pending-jobs 2>/dev/null || echo "")
  if [[ -n "$pending" ]]; then
    echo "Заданий в очереди: ${pending}"
    if [[ "$pending" -ge 50 ]]; then sustained "queue" "В очереди воркера ${pending} заданий — воркер не справляется или упал"; else clear_flag queue; fi
  fi

  # ── бэкапы без свежей успешной копии ────────────────────────────────
  stale=$("$PHP_BIN" "$HELPER" stale-backups --days=2 2>/dev/null || echo "")
  if [[ -n "$stale" ]]; then
    alert "Нет свежего успешного бэкапа (>2 дней) у: $(echo "$stale" | tr '\n' ' ')"
  fi

  # ── злоупотребления по клиентам: CPU/RAM/процессы сверх тарифа ──────
  while IFS=$'\t' read -r cuser cpu_limit mem_limit disk_limit inode_limit tasks_limit; do
    [[ -z "$cuser" ]] && continue
    procs=$(pgrep -u "$cuser" 2>/dev/null | wc -l)
    if [[ "$procs" -gt 0 ]]; then
      cpu_used=$(ps -u "$cuser" -o %cpu= 2>/dev/null | awk '{s+=$1} END{printf "%.1f", s}')
      mem_used_kb=$(ps -u "$cuser" -o rss= 2>/dev/null | awk '{s+=$1} END{print s+0}')
      mem_used_mb=$(( mem_used_kb / 1024 ))

      "$PHP_BIN" "$HELPER" record-usage --user="$cuser" --cpu="${cpu_used:-0}" \
        --mem="$mem_used_mb" --procs="$procs" >/dev/null 2>&1

      if [[ "$tasks_limit" -gt 0 && "$procs" -ge $(( tasks_limit * 80 / 100 )) ]]; then
        sustained "procs-${cuser}" "${cuser}: ${procs} процессов (лимит ${tasks_limit}) — близко к пределу"
      else
        clear_flag "procs-${cuser}"
      fi
    fi
  done < <("$PHP_BIN" "$HELPER" client-limits 2>/dev/null)
fi

# ── истечение SSL (базовый домен + wildcard) ────────────────────────────
if [[ -n "${HOSTING_ROOT_DOMAIN:-}" ]] && command -v openssl >/dev/null 2>&1; then
  CERT="/etc/letsencrypt/live/${HOSTING_ROOT_DOMAIN}/fullchain.pem"
  if [[ -f "$CERT" ]]; then
    expiry=$(openssl x509 -enddate -noout -in "$CERT" 2>/dev/null | cut -d= -f2)
    if [[ -n "$expiry" ]]; then
      expiry_ts=$(date -d "$expiry" +%s 2>/dev/null || echo 0)
      now_ts=$(date +%s)
      days_left=$(( (expiry_ts - now_ts) / 86400 ))
      echo "SSL ${HOSTING_ROOT_DOMAIN}: истекает через ${days_left} дн."
      [[ "$days_left" -le 14 ]] && alert "SSL-сертификат ${HOSTING_ROOT_DOMAIN} истекает через ${days_left} дн."
    fi
  fi
fi

echo "=== monitor.sh готово ==="
