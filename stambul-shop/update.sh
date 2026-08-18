#!/usr/bin/env bash
# Обновление магазина одной командой: код, сборка, схема, перезапуск,
# перенос ключей из .env и проверка, что всё действительно доехало.
#
# Запуск:  bash update.sh
set -euo pipefail

cd "$(dirname "$0")"
BRANCH="${BRANCH:-claude/telegram-bot-rental-sales-um5rrj}"

GREEN=$'\033[32m'; RED=$'\033[31m'; OFF=$'\033[0m'
say()  { echo "${GREEN}▸${OFF} $*"; }
die()  { echo "${RED}!${OFF} $*"; exit 1; }

[ -f .env ] || die "Нет файла .env — сначала пройдите install.sh"

# ─────────────────────────── Код ───────────────────────────

say "Забираю обновления"
for attempt in 1 2 3 4; do
    git fetch origin "$BRANCH" && break
    echo "  сеть подвела, повтор через $((2 ** attempt)) с"
    sleep $((2 ** attempt))
done
git reset --hard "origin/$BRANCH" >/dev/null
say "Код: $(git log --oneline -1)"

# ─────────────────────────── Сборка ───────────────────────────

# Образ у api, bot, worker и migrate общий — одной сборки хватает всем.
# Отдельно web: у него свой Dockerfile.
say "Собираю образы. В первый раз с обработкой фотографий это 5–15 минут"
docker compose build api web || die "Сборка не прошла — покажите последние строки выше"

# Бывает, что образ собрался, а свежих файлов в нём нет: обычно из-за
# кэша слоёв. Проверяем сразу и, если так, пересобираем начисто — лучше
# лишние десять минут, чем «обновил, а ничего не поменялось».
if ! docker compose run --rm --no-deps -T api \
        test -f app/bot/handlers/add_product.py 2>/dev/null; then
    say "В образе нет новых файлов — пересобираю начисто"
    docker compose build --no-cache api || die "Сборка начисто не прошла"
fi

# ─────────────────────────── Схема ───────────────────────────

say "Обновляю схему базы"
docker compose run --rm migrate || die "Миграция не прошла"

# ─────────────────────────── Запуск ───────────────────────────

say "Перезапускаю контейнеры"
docker compose up -d --force-recreate --remove-orphans

say "Жду, пока поднимется API"
API_PORT="$(grep -E '^API_PORT=' .env | cut -d= -f2- || echo 8010)"
for _ in $(seq 1 40); do
    curl -sf "http://127.0.0.1:${API_PORT:-8010}/health" >/dev/null && break
    sleep 2
done
curl -sf "http://127.0.0.1:${API_PORT:-8010}/health" >/dev/null \
    || die "API не отвечает: docker compose logs --tail=40 api"

# ─────────────────────── Ключи из .env в настройки ───────────────────────

say "Переношу ключи из .env"
docker compose exec -T api python -m app.db.settings_from_env \
    || echo "  не вышло — ключ можно вписать в панели"

# ─────────────────────────── Проверка ───────────────────────────

echo
say "Проверяю, что новое действительно доехало"
fail=0
check() {
    if eval "$2" >/dev/null 2>&1; then
        echo "   ✓ $1"
    else
        echo "   ${RED}✗ $1${OFF}"
        fail=1
    fi
}
check "мастер добавления товара в боте" \
      "docker compose exec -T bot test -f app/bot/handlers/add_product.py"
check "разбор фотографий" \
      "docker compose exec -T bot python -c 'import app.services.ai_vision'"
check "обработка фона" \
      "docker compose exec -T bot python -c 'import app.imaging.pipeline'"
check "витрина отвечает" \
      "curl -sf http://127.0.0.1:$(grep -E '^WEB_PORT=' .env | cut -d= -f2- || echo 8100)"

echo
docker compose ps --format '   {{.Service}}\t{{.Status}}'
echo

[ "$fail" = 0 ] || die "Что-то не доехало — покажите строки выше"

DOMAIN="$(grep -E '^DOMAIN=' .env | cut -d= -f2- || true)"
say "Готово. Магазин: https://${DOMAIN:-ваш-домен}"
echo
echo "Дальше в Telegram:"
echo "  /start   — обновит меню, появится «➕ Добавить товар»"
echo "  /add     — завести товар: фото → раздел → цена → публикация"
echo
echo "На сайте вкладку лучше закрыть и открыть заново: браузер держит"
echo "старую версию, и раздел «Настройки» иначе не покажется."
