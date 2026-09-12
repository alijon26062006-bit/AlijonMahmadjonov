#!/usr/bin/env bash
#
# AVERIX — one command from a bare server to a running site.
#
#   ./install.sh
#
# It installs Docker if the machine does not have it, generates the secrets,
# writes .env, builds the images, applies the migrations, starts everything and
# waits until the site answers. Safe to run again: existing secrets are kept,
# and re-running is how you deploy a new version.
#
#   ./install.sh --domain averix.dev --email you@averix.dev
#   ./install.sh --dev          # localhost, no certificate, no domain needed

set -euo pipefail

DOMAIN="${AVERIX_DOMAIN:-averix.dev}"
EMAIL="${ACME_EMAIL:-}"
MODE="production"
COMPOSE_FILE="docker-compose.production.yml"

while [ $# -gt 0 ]; do
  case "$1" in
    --domain) DOMAIN="$2"; shift 2 ;;
    --email)  EMAIL="$2";  shift 2 ;;
    --dev)    MODE="development"; COMPOSE_FILE="docker-compose.yml"; shift ;;
    -h|--help)
      sed -n '3,14p' "$0" | sed 's/^#\( \|$\)//'
      exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done

cd "$(dirname "$0")"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m!  %s\033[0m\n' "$*"; }
fail() { printf '\033[31m✗  %s\033[0m\n' "$*" >&2; exit 1; }
ok()   { printf '\033[32m✓\033[0m  %s\n' "$*"; }

echo
bold "AVERIX installer"
echo

# ── 1. Docker ───────────────────────────────────────────────────────────────

if ! command -v docker >/dev/null 2>&1; then
  bold "Installing Docker"
  curl -fsSL https://get.docker.com | sh || fail "Docker could not be installed. Install it and run this again."
  ok "Docker installed"
else
  ok "Docker $(docker version --format '{{.Server.Version}}' 2>/dev/null || echo present)"
fi

if ! docker compose version >/dev/null 2>&1; then
  fail "This Docker has no compose plugin. Install docker-compose-plugin and run this again."
fi

if ! docker info >/dev/null 2>&1; then
  fail "The Docker daemon is not running. Start it with: systemctl start docker"
fi

# ── 2. Configuration ────────────────────────────────────────────────────────

secret() { openssl rand -hex 32; }

if [ "$MODE" = "production" ]; then
  if [ ! -f .env ]; then
    bold "Writing .env"

    if [ -z "$EMAIL" ]; then
      EMAIL="admin@${DOMAIN}"
      warn "Using $EMAIL for certificate notices. Change ACME_EMAIL in .env if that address does not exist."
    fi

    # Start from the example so every option stays documented in the file the
    # operator will actually edit, then fill in the values that must be real.
    cp .env.example .env
    python3 - "$DOMAIN" "$EMAIL" <<'PY'
import re, sys, secrets
domain, email = sys.argv[1], sys.argv[2]
text = open('.env').read()

def put(key, value):
    global text
    pattern = rf'^{key}=.*$'
    text = re.sub(pattern, f'{key}={value}', text, count=1, flags=re.M)

put('AVERIX_DOMAIN', domain)
put('ACME_EMAIL', email)
put('APP_URL', f'https://{domain}')
put('API_URL', f'https://{domain}')
put('GITHUB_CALLBACK_URL', f'https://{domain}/api/v1/github/callback')
put('S3_PUBLIC_BASE_URL', f'https://{domain}/api/v1/files')
put('MAIL_FROM_ADDRESS', f'no-reply@{domain}')

# Three independent secrets and a database password. Generated here so no
# human ever has to invent one, and never printed to the terminal.
put('COOKIE_SECRET', secrets.token_hex(32))
put('DATA_ENCRYPTION_KEY', secrets.token_hex(32))
put('AI_SERVICE_TOKEN', secrets.token_hex(32))
put('POSTGRES_PASSWORD', secrets.token_hex(24))

open('.env', 'w').write(text)
PY
    chmod 600 .env
    ok ".env written for $DOMAIN (secrets generated, file readable only by you)"
  else
    ok ".env already exists — keeping it, including its secrets"
    DOMAIN="$(grep -E '^AVERIX_DOMAIN=' .env | cut -d= -f2- || echo "$DOMAIN")"
  fi

  # ── 3. DNS ────────────────────────────────────────────────────────────────
  # Not fatal: DNS may still be propagating, and Caddy will keep trying. But
  # saying so now beats a mysterious certificate failure later.
  resolved="$(getent hosts "$DOMAIN" 2>/dev/null | awk '{print $1}' | head -1 || true)"
  public="$(curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null || true)"
  if [ -n "$resolved" ] && [ -n "$public" ]; then
    if [ "$resolved" = "$public" ]; then
      ok "DNS: $DOMAIN → $public"
    else
      warn "$DOMAIN resolves to $resolved but this server is $public."
      warn "The certificate cannot be issued until the A record points here."
    fi
  elif [ -z "$resolved" ]; then
    warn "$DOMAIN does not resolve yet. Point its A record at this server; Caddy will retry."
  fi
fi

# ── 4. Build and start ──────────────────────────────────────────────────────

bold "Building images (a few minutes the first time)"
docker compose -f "$COMPOSE_FILE" build --pull

bold "Starting"
docker compose -f "$COMPOSE_FILE" up -d

# ── 5. Wait until it actually answers ───────────────────────────────────────

bold "Waiting for the stack to become ready"
ready=""
for attempt in $(seq 1 60); do
  if docker compose -f "$COMPOSE_FILE" exec -T api /usr/local/bin/averixctl healthcheck >/dev/null 2>&1; then
    ready="yes"
    break
  fi
  sleep 2
  printf '.'
done
echo

if [ -z "$ready" ]; then
  warn "The API did not become healthy in two minutes."
  echo "  Look at: docker compose -f $COMPOSE_FILE logs api"
  exit 1
fi
ok "API healthy"

# Read the readiness report from a container that has a shell: the API image
# is distroless and deliberately has neither wget nor sh in it.
probe="caddy"
[ "$MODE" = "development" ] && probe="web"
status="$(docker compose -f "$COMPOSE_FILE" exec -T "$probe" \
  wget -qO- --timeout=5 http://api:8080/ready 2>/dev/null || true)"
if [ -n "$status" ]; then
  echo "  $(echo "$status" | head -c 400)"
fi

# ── 6. What now ─────────────────────────────────────────────────────────────

echo
bold "AVERIX is running"
echo
if [ "$MODE" = "production" ]; then
  echo "  Site        https://$DOMAIN"
  echo "  Health      https://$DOMAIN/ready"
  echo
  echo "  The certificate is issued on the first request. If the site does not"
  echo "  load, check that ports 80 and 443 are open and the A record points here."
else
  echo "  Site        http://localhost:3000"
  echo "  API         http://localhost:8080/health"
fi
echo
echo "Next:"
echo "  1. Sign up on the site, then make yourself an administrator:"
echo "       docker compose -f $COMPOSE_FILE exec api averixctl create-admin --email you@$DOMAIN"
echo "  2. In the admin panel, open Payments and enter the transfer details."
echo "  3. Turn on backups:"
echo "       (crontab -l 2>/dev/null; echo \"0 3 * * * cd $(pwd) && ./scripts/backup.sh >> /var/log/averix-backup.log 2>&1\") | crontab -"
echo
echo "Useful:"
echo "  docker compose -f $COMPOSE_FILE ps"
echo "  docker compose -f $COMPOSE_FILE logs -f api"
echo "  ./install.sh          # run again to deploy a new version"
echo
