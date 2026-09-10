#!/usr/bin/env bash
# ЕДИНСТВЕННАЯ команда, которая нужна на сервере:
#
#   sudo bash hosting/go.sh
#
# Она сама обновляет репозиторий до нужной ветки, ставит и настраивает всё ПО
# (install.sh), спрашивает домен/бота/пароль администратора (setup.sh) и в конце
# проверяет весь хостинг целиком (scripts/doctor.sh).
#
# Запускать повторно безопасно: каждый шаг идемпотентен, ответы подставляются
# из текущего .env — на том, что менять не нужно, достаточно жать Enter.

set -uo pipefail

BRANCH="${HOSTING_BRANCH:-claude/php-hosting-someonhost-1yxfl9}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

log()  { echo -e "\033[1;32m==>\033[0m $*"; }
warn() { echo -e "\033[1;33m!!\033[0m $*" >&2; }
die()  { echo -e "\033[1;31mОШИБКА:\033[0m $*" >&2; exit 1; }
step() { echo; echo -e "\033[1;44m ШАГ $1 из 3 \033[0m \033[1m$2\033[0m"; echo; }

[[ $EUID -eq 0 ]] || die "Запустите от root: sudo bash hosting/go.sh"

# ── 0. обновление репозитория ───────────────────────────────────────────────
#
# Самая частая причина «No such file or directory»: локальный клон стоит на
# другой ветке, а файлов hosting/ на ней нет. Чиним это сами, а не просьбой
# к человеку выполнить git checkout.
#
# После обновления перезапускаем сами себя уже новой версией скрипта —
# HOSTING_GO_UPDATED защищает от бесконечного цикла.
if [[ -z "${HOSTING_GO_UPDATED:-}" ]] && command -v git >/dev/null 2>&1 && [[ -d "${REPO_ROOT}/.git" ]]; then
  log "Обновляю репозиторий до ветки ${BRANCH}"
  cd "$REPO_ROOT" || die "Не могу перейти в ${REPO_ROOT}"

  if ! git diff --quiet || ! git diff --cached --quiet; then
    warn "В репозитории есть несохранённые правки — обновление пропускаю, работаю с тем, что есть"
  else
    git fetch origin "$BRANCH" --quiet 2>/dev/null || warn "git fetch не удался — работаю с локальной версией"
    CURRENT=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
    if [[ "$CURRENT" != "$BRANCH" ]]; then
      git checkout "$BRANCH" --quiet 2>/dev/null || git checkout -b "$BRANCH" "origin/${BRANCH}" --quiet 2>/dev/null \
        || warn "Не удалось переключиться на ${BRANCH}"
    fi
    git merge --ff-only "origin/${BRANCH}" --quiet 2>/dev/null || true
    log "Версия кода: $(git rev-parse --short HEAD) ($(git rev-parse --abbrev-ref HEAD))"
  fi

  if [[ -f "${REPO_ROOT}/hosting/go.sh" ]]; then
    export HOSTING_GO_UPDATED=1
    exec bash "${REPO_ROOT}/hosting/go.sh" "$@"
  fi
fi

[[ -f "${SCRIPT_DIR}/install.sh" ]] || die "Не нахожу ${SCRIPT_DIR}/install.sh — вы точно в каталоге репозитория?"

cat <<BANNER

  Установка хостинга. Три шага, примерно 5–10 минут.

    1. Ставлю и настраиваю ПО (nginx, PHP, MariaDB, firewall) — вопросов не будет
    2. Спрошу домен, токен бота и пароль администратора
    3. Проверю всё целиком и покажу, что работает, а что нет

BANNER

# ── 1. install.sh ───────────────────────────────────────────────────────────
step 1 "Установка ПО"
if bash "${SCRIPT_DIR}/install.sh"; then
  log "ПО установлено"
else
  echo
  die "Установка прервалась. Полный лог: /var/log/hosting-install.log
     Последние строки лога:
$(tail -20 /var/log/hosting-install.log 2>/dev/null | sed 's/^/       /')"
fi

# ── 2. setup.sh ─────────────────────────────────────────────────────────────
step 2 "Настройка (сейчас будут вопросы)"
if bash "${SCRIPT_DIR}/setup.sh"; then
  log "Настройка завершена"
else
  warn "Мастер настройки завершился с ошибкой — доктор ниже скажет, что именно не так"
fi

# ── 3. doctor.sh ────────────────────────────────────────────────────────────
step 3 "Проверка"
if bash "${SCRIPT_DIR}/scripts/doctor.sh"; then
  echo
  echo -e "\033[1;32m═══════════════════════════════════════════════\033[0m"
  echo -e "\033[1;32m  Хостинг работает и готов принимать клиентов.\033[0m"
  echo -e "\033[1;32m═══════════════════════════════════════════════\033[0m"
  exit 0
else
  echo
  warn "Часть проверок не прошла — что именно, помечено выше как [ПРОБЛЕМА]."
  echo "Повторить проверку в любой момент: sudo bash ${SCRIPT_DIR}/scripts/doctor.sh"
  echo "Повторить всю установку целиком:   sudo bash ${SCRIPT_DIR}/go.sh"
  exit 1
fi
