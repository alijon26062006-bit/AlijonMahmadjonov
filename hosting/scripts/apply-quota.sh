#!/usr/bin/env bash
# Применяет дисковую квоту клиента на уровне файловой системы — хранить лимит
# только в БД панели недостаточно (см. спецификацию, раздел DISK QUOTA).
#
# Использование: apply-quota.sh <system_user> <disk_quota_mb> <inode_limit>
# Вызывается root-воркером (см. worker/src/JobHandler::handleApplyQuota).
#
# Поддерживает два варианта:
#   1. XFS с project quota (рекомендуется — используйте XFS под /home/hosting)
#   2. ext4 с quota (usrquota/grpquota в fstab) — квота вешается на unix-пользователя
# Если ни один не настроен — предупреждает и выходит успешно (0), чтобы не блокировать
# остальной провижининг; фактическое ограничение тогда только "мягкое" — через
# periodic monitor.sh + suspend_site при превышении (см. monitor.sh).

set -euo pipefail

PANEL_NAME="${PANEL_NAME:-AlijonHost}"
USER="${1:?Использование: apply-quota.sh <system_user> <disk_quota_mb> <inode_limit>}"
DISK_MB="${2:?нужен лимит диска в МБ}"
INODES="${3:?нужен лимит inode}"
HOME_DIR="${HOSTING_USERS_ROOT:-/home/hosting}/${USER}"

if [[ ! "$USER" =~ ^client[0-9]{1,10}$ ]]; then
  echo "[apply-quota] отказ: недопустимое имя пользователя '$USER'" >&2
  exit 1
fi
if [[ ! "$DISK_MB" =~ ^[0-9]+$ || ! "$INODES" =~ ^[0-9]+$ ]]; then
  echo "[apply-quota] отказ: лимиты должны быть числами" >&2
  exit 1
fi

FSTYPE=$(findmnt -n -o FSTYPE --target "$HOME_DIR" 2>/dev/null || echo "unknown")

if [[ "$FSTYPE" == "xfs" ]] && command -v xfs_quota >/dev/null 2>&1; then
  MOUNTPOINT=$(findmnt -n -o TARGET --target "$HOME_DIR")
  PROJECT_ID=$(id -u "$USER")
  xfs_quota -x -c "project -s -p $HOME_DIR $PROJECT_ID" "$MOUNTPOINT" >/dev/null
  xfs_quota -x -c "limit -p bhard=${DISK_MB}m ihard=${INODES} ${PROJECT_ID}" "$MOUNTPOINT"
  echo "[apply-quota] $USER: XFS project quota — ${DISK_MB}MB / ${INODES} inode"
  exit 0
fi

if [[ "$FSTYPE" == "ext4" ]] && command -v setquota >/dev/null 2>&1; then
  MOUNTPOINT=$(findmnt -n -o TARGET --target "$HOME_DIR")
  BLOCKS=$((DISK_MB * 1024))
  setquota -u "$USER" "$BLOCKS" "$BLOCKS" "$INODES" "$INODES" "$MOUNTPOINT"
  echo "[apply-quota] $USER: ext4 usrquota — ${DISK_MB}MB / ${INODES} inode"
  exit 0
fi

echo "[apply-quota] ПРЕДУПРЕЖДЕНИЕ: файловая система '$FSTYPE' под $HOME_DIR не поддерживает" >&2
echo "  project/user quota в этой установке (нет xfs_quota/setquota). Лимит применяется" >&2
echo "  только 'мягко' — через периодическую проверку scripts/monitor.sh и suspend_site" >&2
echo "  при превышении. Для жёсткой квоты используйте XFS с project quota под ${HOSTING_USERS_ROOT:-/home/hosting}." >&2
exit 0
