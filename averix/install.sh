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
#   ./install.sh --behind-nginx # this server's Nginx keeps ports 80 and 443
#   ./install.sh --dev          # localhost, no certificate, no domain needed

set -euo pipefail

DOMAIN="${AVERIX_DOMAIN:-averix.dev}"
# Set when the domain does not point here; repeated in the closing summary.
DNS_VERDICT=""
EMAIL="${ACME_EMAIL:-}"
MODE="production"
COMPOSE_FILE="docker-compose.production.yml"
# "caddy"  — the stack owns ports 80 and 443 and gets its own certificate.
# "nginx"  — this server's own Nginx owns them; the stack sits behind it.
# "auto"   — decide by looking at what is listening.
FRONT="auto"

while [ $# -gt 0 ]; do
  case "$1" in
    --domain) DOMAIN="$2"; shift 2 ;;
    --email)  EMAIL="$2";  shift 2 ;;
    --behind-nginx) FRONT="nginx"; shift ;;
    --with-caddy)   FRONT="caddy"; shift ;;
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

# ── 1b. Container DNS ───────────────────────────────────────────────────────
#
# A build resolves names from inside the container, not from the host. On a
# good many VPS images those are different things: the host talks to its
# provider's resolver happily while the container's NAT'd traffic is dropped
# or ignored, and every build dies on "i/o timeout" fetching dependencies.
#
# This checks it before spending ten minutes finding out, and fixes it by
# giving the daemon public resolvers — the same thing an operator would do by
# hand, written down so nobody has to know it.

dns_works() {
  docker run --rm --pull=never alpine:3 \
    sh -c 'nslookup proxy.golang.org >/dev/null 2>&1 || getent hosts proxy.golang.org >/dev/null 2>&1' \
    >/dev/null 2>&1
}

bold "Checking DNS inside containers"
if ! docker image inspect alpine:3 >/dev/null 2>&1; then
  docker pull -q alpine:3 >/dev/null 2>&1 || true
fi

if ! docker image inspect alpine:3 >/dev/null 2>&1; then
  # Without the probe image there is nothing to test with. Saying so beats
  # "fixing" DNS on the strength of a failed image pull.
  warn "Could not fetch the probe image, so container DNS was not checked."
  warn "If the build fails with \"i/o timeout\" on a dependency, this is why."
elif dns_works; then
  ok "Containers can resolve names"
else
  warn "Containers cannot resolve names — builds would fail fetching dependencies."
  echo "   Pointing the Docker daemon at public resolvers (1.1.1.1, 8.8.8.8)…"

  python3 - <<'PYEOF'
import json, os

path = '/etc/docker/daemon.json'
config = {}
if os.path.exists(path):
    try:
        with open(path) as handle:
            config = json.load(handle) or {}
    except ValueError:
        # A hand-edited file with a trailing comma should not cost someone
        # their other daemon settings silently: keep it and say so.
        backup = path + '.broken'
        os.rename(path, backup)
        print(f'   the existing {path} was not valid JSON; kept as {backup}')
        config = {}

# Only the resolvers are set. Anything else already configured is preserved.
config['dns'] = ['1.1.1.1', '8.8.8.8']
os.makedirs('/etc/docker', exist_ok=True)
with open(path, 'w') as handle:
    json.dump(config, handle, indent=2)
    handle.write('\n')
PYEOF

  if command -v systemctl >/dev/null 2>&1; then
    systemctl restart docker
  else
    service docker restart
  fi

  # The daemon takes a moment to come back.
  for _ in $(seq 1 20); do
    docker info >/dev/null 2>&1 && break
    sleep 1
  done

  if dns_works; then
    ok "Fixed: containers can resolve names now"
  else
    warn "Containers still cannot resolve names."
    echo "   Two things to check on this server:"
    echo "     1. A firewall dropping forwarded traffic:"
    echo "          iptables -P FORWARD ACCEPT"
    echo "          ufw default allow routed        # if ufw is in use"
    echo "     2. Whether the host itself resolves:"
    echo "          getent hosts proxy.golang.org"
    fail "Fix DNS for containers, then run ./install.sh again."
  fi
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
  # saying so now beats a mysterious certificate failure later — and it is
  # repeated at the very end, because a warning in the middle of a build
  # scrolls away long before anyone reads it.
  #
  # Both families are checked. A server with only an IPv6 address needs an
  # AAAA record, and comparing it against an A record would report a mismatch
  # that is really a missing record.
  ipv4="$(curl -4 -fsS --max-time 5 https://api.ipify.org 2>/dev/null || true)"
  ipv6="$(curl -6 -fsS --max-time 5 https://api6.ipify.org 2>/dev/null || true)"
  resolved="$(getent ahosts "$DOMAIN" 2>/dev/null | awk '{print $1}' | sort -u || true)"

  DNS_VERDICT=""
  if [ -z "$resolved" ]; then
    DNS_VERDICT="$DOMAIN does not resolve. No certificate can be issued until it does."
  elif { [ -n "$ipv4" ] && printf '%s\n' "$resolved" | grep -qx "$ipv4"; } \
    || { [ -n "$ipv6" ] && printf '%s\n' "$resolved" | grep -qx "$ipv6"; }; then
    ok "DNS: $DOMAIN points at this server"
  else
    DNS_VERDICT="$DOMAIN points at $(printf '%s' "$resolved" | tr '\n' ' '), which is not this server."
  fi

  if [ -n "$DNS_VERDICT" ]; then
    warn "$DNS_VERDICT"
    [ -n "$ipv4" ] && echo "  This server's IPv4: $ipv4   (A record)"
    [ -n "$ipv6" ] && echo "  This server's IPv6: $ipv6   (AAAA record)"
    [ -z "$ipv4" ] && warn "This server has no IPv4 address. Visitors on IPv4-only networks will not reach it."
  fi
fi

# ── 3b. Who owns ports 80 and 443 ───────────────────────────────────────────
#
# The stack ships with Caddy, which gets and renews the certificate itself.
# That only works if it can bind both ports. Plenty of servers already run
# Nginx — a hosting panel, another site — and taking that down to make room
# is not a decision an installer gets to make on someone's behalf.
#
# So when something else is already listening, AVERIX goes behind it instead.

port_owner() {
  command -v ss >/dev/null 2>&1 || return 0
  ss -lntpH "( sport = :$1 )" 2>/dev/null \
    | grep -o 'users:(("[^"]*"' | head -1 | sed 's/.*(("//;s/"//' || true
}

if [ "$MODE" = "production" ] && [ "$FRONT" = "auto" ]; then
  owner="$(port_owner 80)"
  case "$owner" in
    ""|docker-proxy|caddy) FRONT="caddy" ;;
    *)
      FRONT="nginx"
      bold "Port 80 belongs to $owner"
      echo "  AVERIX will run behind it rather than stopping it. Its own proxy"
      echo "  stays switched off. Force the other way with --with-caddy."
      if [ "$owner" != "nginx" ]; then
        warn "Only Nginx can be configured automatically, and $owner is not Nginx."
        echo "  Proxy $DOMAIN to 127.0.0.1:3000, and /api/ to 127.0.0.1:8080."
      fi
      ;;
  esac
fi
if [ "$FRONT" = "auto" ]; then FRONT="caddy"; fi

# Behind Nginx the stack has to publish two host ports, and on a server that
# already runs Nginx those are exactly the ports something else has taken —
# 3000 and 8080 are the first any application claims. Binding them blindly
# either fails outright or, worse, quietly leaves Nginx pointed at somebody
# else's container. So the ports are chosen, recorded in .env, and the Nginx
# site is generated to match. A port already recorded is kept: it is ours.
port_is_free() {
  ! ss -lnt "( sport = :$1 )" 2>/dev/null | grep -q LISTEN
}

pick_host_port() {   # $1 = variable name in .env, $2 = first port to try
  existing="$(grep -E "^$1=" .env 2>/dev/null | cut -d= -f2- || true)"
  if [ -n "$existing" ]; then printf '%s' "$existing"; return; fi
  candidate="$2"
  while [ "$candidate" -lt 65000 ]; do
    if port_is_free "$candidate"; then printf '%s' "$candidate"; return; fi
    candidate=$((candidate + 1))
  done
  printf '%s' "$2"
}

set_env_var() {      # $1 = key, $2 = value
  AVERIX_SET_KEY="$1" AVERIX_SET_VALUE="$2" python3 - <<'PYEOF'
import os

key, value = os.environ['AVERIX_SET_KEY'], os.environ['AVERIX_SET_VALUE']
with open('.env') as handle:
    lines = handle.read().splitlines()

for index, line in enumerate(lines):
    if line.split('=', 1)[0].strip() == key:
        lines[index] = f'{key}={value}'
        break
else:
    lines.append(f'{key}={value}')

with open('.env', 'w') as handle:
    handle.write('\n'.join(lines) + '\n')
PYEOF
}

WEB_HOST_PORT=3000
API_HOST_PORT=8080
if [ "$MODE" = "production" ] && [ "$FRONT" = "nginx" ]; then
  WEB_HOST_PORT="$(pick_host_port AVERIX_WEB_HOST_PORT 13000)"
  API_HOST_PORT="$(pick_host_port AVERIX_API_HOST_PORT 18080)"
  set_env_var AVERIX_WEB_HOST_PORT "$WEB_HOST_PORT"
  set_env_var AVERIX_API_HOST_PORT "$API_HOST_PORT"
  ok "Publishing on 127.0.0.1:$WEB_HOST_PORT (site) and 127.0.0.1:$API_HOST_PORT (API)"
fi

# Every compose invocation below goes through this, so the overlay is applied
# in one place rather than remembered at a dozen call sites.
COMPOSE=(docker compose -f "$COMPOSE_FILE")
COMPOSE_SHOW="docker compose -f $COMPOSE_FILE"
UP_ARGS=()
if [ "$FRONT" = "nginx" ]; then
  COMPOSE+=(-f docker-compose.nginx.yml)
  COMPOSE_SHOW="$COMPOSE_SHOW -f docker-compose.nginx.yml"
  # Scaled to zero rather than removed: one stack definition, and going back
  # to Caddy is dropping the overlay.
  UP_ARGS+=(--scale caddy=0)
fi

# ── 4. Build and start ──────────────────────────────────────────────────────

bold "Building images (a few minutes the first time)"
"${COMPOSE[@]}" build --pull

# The API and the worker run as uid 65532 and write uploads to a named
# volume. Docker creates a volume owned by root, and seeds ownership from the
# image only while the volume is still empty — so a volume created before the
# image carried that directory stays unwritable forever. One chown settles it
# either way, and it touches nothing but the owner, so a volume with real
# uploads in it is safe.
volume="$(docker volume ls --format '{{.Name}}' 2>/dev/null \
  | grep -E '_averix-storage$' | head -1 || true)"
[ -n "$volume" ] || volume="averix_averix-storage"
if docker run --rm -v "$volume:/data/storage" alpine:3 \
     chown -R 65532:65532 /data/storage >/dev/null 2>&1; then
  ok "Uploads volume is writable by the application"
else
  warn "Could not set ownership on the uploads volume ($volume)."
  echo "  If the API reports \"permission denied\" on /data/storage, run:"
  echo "    docker run --rm -v $volume:/data/storage alpine:3 chown -R 65532:65532 /data/storage"
fi

bold "Starting"
if ! "${COMPOSE[@]}" up -d ${UP_ARGS[@]+"${UP_ARGS[@]}"}; then
  # Compose names the service that failed but never says why, and the
  # container is usually gone by the time anyone goes looking. Print the
  # reason here — and only for the containers that actually failed, so the
  # answer is the last thing on screen rather than scrolled away above the
  # logs of everything that was merely waiting.
  echo
  broken=""
  for service in $("${COMPOSE[@]}" config --services); do
    container="$("${COMPOSE[@]}" ps -aq "$service" 2>/dev/null | head -1)"
    [ -n "$container" ] || continue
    state="$(docker inspect -f '{{.State.Status}}:{{.State.ExitCode}}' "$container" 2>/dev/null || echo 'unknown:1')"
    case "$state" in
      # Running is fine, exited 0 is a job that finished, and created means
      # the container never got to start because something else failed first.
      running:* | exited:0 | created:*) ;;
      *) broken="$broken $service" ;;
    esac
  done

  if [ -n "$broken" ]; then
    warn "These services failed:$broken"
    for service in $broken; do
      printf '\n----- %s -----\n' "$service"
      "${COMPOSE[@]}" logs --no-color --tail 40 "$service" 2>&1 || true
    done
  else
    warn "No container logged a failure — so it never got far enough to log."
    echo "  Read the \"Error response from daemon\" line above: that is the reason."
    echo "  The stack as it stands:"
    "${COMPOSE[@]}" ps -a
  fi

  # A port already taken is the usual reason a container dies before it can
  # write a single line, and the daemon's message names the port but never
  # what holds it.
  if command -v ss >/dev/null 2>&1; then
    listeners="$(ss -lntp 2>/dev/null | awk 'NR == 1 || $4 ~ /:(80|443)$/' || true)"
    if [ "$(printf '%s\n' "$listeners" | wc -l)" -gt 1 ]; then
      echo
      echo "  Listening on ports 80 and 443 right now:"
      printf '%s\n' "$listeners" | sed 's/^/    /'
      echo "  If that is a web server of the host (nginx, apache, another Caddy),"
      echo "  stop it — this stack needs both ports:"
      echo "      systemctl disable --now nginx apache2 caddy"
    fi
  fi

  echo
  fail "Fix what the logs above report, then run ./install.sh again."
fi

# ── 4b. Does the stack's own network have a way out? ────────────────────────
#
# The DNS probe earlier runs on Docker's default bridge. The stack runs on a
# network of its own, and the two are not the same thing: a project network
# created while the daemon was still misconfigured can come up without the
# rules that give it a route off the host. Every container on it then gets
# "network is unreachable" while the probe on the default bridge passes
# happily — and the only symptom is Caddy never obtaining a certificate,
# hours later, in a log nobody is reading.
#
# Recreating the network is what fixes it, and `down` plus `up` is exactly
# that. It costs a few seconds and no data: everything durable is in volumes.

project_network() {
  container="$("${COMPOSE[@]}" ps -q caddy 2>/dev/null | head -1)"
  [ -n "$container" ] || container="$("${COMPOSE[@]}" ps -q web 2>/dev/null | head -1)"
  [ -n "$container" ] || return 0
  docker inspect -f '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{"\n"}}{{end}}' \
    "$container" 2>/dev/null | head -1
}

network_has_egress() {
  docker run --rm --pull=never --network "$1" alpine:3 \
    sh -c 'nslookup acme-v02.api.letsencrypt.org >/dev/null 2>&1' >/dev/null 2>&1
}

if docker image inspect alpine:3 >/dev/null 2>&1; then
  network="$(project_network)"
  if [ -n "$network" ] && ! network_has_egress "$network"; then
    warn "The stack's network ($network) has no route to the internet."
    echo "   Recreating it. Nothing is lost: the data is in volumes."
    "${COMPOSE[@]}" down >/dev/null 2>&1 || true
    "${COMPOSE[@]}" up -d ${UP_ARGS[@]+"${UP_ARGS[@]}"}

    network="$(project_network)"
    if [ -n "$network" ] && network_has_egress "$network"; then
      ok "Fixed: the stack can reach the internet"
    else
      warn "It still cannot. Without this no certificate can be issued."
      echo "   Usually a firewall dropping forwarded traffic:"
      echo "     iptables -P FORWARD ACCEPT"
      echo "     ufw default allow routed        # if ufw is in use"
    fi
  fi
fi

# ── 5. Wait until it actually answers ───────────────────────────────────────

bold "Waiting for the stack to become ready"
ready=""
for attempt in $(seq 1 60); do
  if "${COMPOSE[@]}" exec -T api /usr/local/bin/averixctl healthcheck >/dev/null 2>&1; then
    ready="yes"
    break
  fi
  sleep 2
  printf '.'
done
echo

if [ -z "$ready" ]; then
  warn "The API did not become healthy in two minutes."
  echo "  Look at: $COMPOSE_SHOW logs api"
  exit 1
fi
ok "API healthy"

# Read the readiness report from a container that has a shell: the API image
# is distroless and deliberately has neither wget nor sh in it.
probe="caddy"
if [ "$MODE" = "development" ] || [ "$FRONT" = "nginx" ]; then probe="web"; fi
status="$("${COMPOSE[@]}" exec -T "$probe" \
  wget -qO- --timeout=5 http://api:8080/ready 2>/dev/null || true)"
if [ -n "$status" ]; then
  echo "  $(echo "$status" | head -c 400)"
fi

# ── 5b. The site on this server's own Nginx ─────────────────────────────────
#
# Two passes, because of an ordering problem that otherwise leaves an operator
# with an Nginx that will not start: a server block referring to a certificate
# file that does not exist yet fails `nginx -t`, and the certificate cannot be
# issued until Nginx is serving the challenge over port 80.
#
# So: write the plain HTTP site first and reload, obtain the certificate
# through it, then write the same site with TLS and reload again. Re-running
# is safe — an existing certificate skips straight to the second pass.

# Where a site file on this server is actually picked up. A directory
# existing proves nothing — a hosting panel can ship sites-enabled and never
# include it — so this goes by what nginx.conf includes.
nginx_site_path() {
  if grep -qs 'sites-enabled' /etc/nginx/nginx.conf; then
    echo "/etc/nginx/sites-available/averix.conf"
  elif grep -qs 'conf\.d' /etc/nginx/nginx.conf; then
    echo "/etc/nginx/conf.d/averix.conf"
  else
    echo ""
  fi
}

# Renders the templates. $1 is "http" for the first pass, "tls" for the second.
write_nginx_site() {
  target="$(nginx_site_path)"
  if [ -z "$target" ]; then
    warn "This Nginx includes neither sites-enabled nor conf.d."
    echo "  Add the site by hand: proxy $DOMAIN to 127.0.0.1:3000,"
    echo "  and /api/ to 127.0.0.1:8080."
    return 1
  fi
  mkdir -p "$(dirname "$target")"
  proxy="$(cat infrastructure/nginx/averix.proxy.template)"

  if [ "$1" = "tls" ]; then
    http_body="    location / { return 301 https://\$host\$request_uri; }"
    tls_server="$(sed "s/__DOMAIN__/$DOMAIN/g" infrastructure/nginx/averix.tls.template)"
    tls_server="${tls_server//__PROXY_BODY__/$proxy}"
  else
    # Before there is a certificate the site answers over plain HTTP rather
    # than redirecting to an address that cannot serve it yet.
    http_body="$proxy"
    tls_server=""
  fi

  site="$(sed -e "s/__DOMAIN__/$DOMAIN/g" \
              -e "s/__WEB_PORT__/$WEB_HOST_PORT/g" \
              -e "s/__API_PORT__/$API_HOST_PORT/g" \
              infrastructure/nginx/averix.conf.template)"
  site="${site//__HTTP_BODY__/$http_body}"
  site="${site//__TLS_SERVER__/$tls_server}"

  printf '%s\n' "$site" > "$target"
  if [ -d /etc/nginx/sites-enabled ]; then
    ln -sf "$target" /etc/nginx/sites-enabled/averix.conf
  fi

  if ! nginx -t >/dev/null 2>&1; then
    warn "The generated Nginx configuration was rejected:"
    nginx -t 2>&1 | sed 's/^/    /'
    rm -f "$target" /etc/nginx/sites-enabled/averix.conf
    nginx -t >/dev/null 2>&1 && systemctl reload nginx >/dev/null 2>&1 || true
    return 1
  fi
  systemctl reload nginx >/dev/null 2>&1 || service nginx reload >/dev/null 2>&1 || true

  # The file passing `nginx -t` is not the same as Nginx serving it: a site
  # written into a directory nothing includes is silently inert.
  if ! nginx -T 2>/dev/null | grep -q "server_name $DOMAIN"; then
    warn "Nginx accepted the file but is not serving $DOMAIN from it ($target)."
    return 1
  fi
  return 0
}

if [ "$MODE" = "production" ] && [ "$FRONT" = "nginx" ]; then
  if ! command -v nginx >/dev/null 2>&1; then
    warn "Nginx owns port 80 but is not on the PATH, so the site was not configured."
    echo "  Proxy $DOMAIN to 127.0.0.1:3000, and /api/ to 127.0.0.1:8080."
  else
    bold "Configuring Nginx for $DOMAIN"
    mkdir -p /var/www/certbot

    # Before pointing Nginx at a port, check that the port answers with this
    # application. A published port that silently belongs to another container
    # gives a site that loads and is somebody else's, which is worse than a
    # site that does not load at all.
    upstream_page="$(curl -fsS --max-time 5 "http://127.0.0.1:$WEB_HOST_PORT/" 2>/dev/null || true)"
    case "$upstream_page" in
      *AVERIX*|*averix*) ok "127.0.0.1:$WEB_HOST_PORT is serving AVERIX" ;;
      "") warn "Nothing answered on 127.0.0.1:$WEB_HOST_PORT. Check: $COMPOSE_SHOW logs web" ;;
      *)  fail "127.0.0.1:$WEB_HOST_PORT is answering, but it is not AVERIX.
   Another container or service holds that port. Remove
   AVERIX_WEB_HOST_PORT from .env and run ./install.sh again to pick another." ;;
    esac


    live="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
    if [ ! -f "$live" ]; then
      if write_nginx_site http; then
        ok "Serving $DOMAIN over HTTP"
      else
        fail "Nginx rejected the site configuration. Nothing was changed."
      fi

      if command -v certbot >/dev/null 2>&1; then
        bold "Requesting the certificate"
        certbot_email=(--register-unsafely-without-email)
        if [ -n "$EMAIL" ]; then certbot_email=(--email "$EMAIL"); fi
        # Only names that actually resolve are requested: one name without a
        # DNS record fails the whole certificate.
        names=(-d "$DOMAIN")
        if getent hosts "www.$DOMAIN" >/dev/null 2>&1; then names+=(-d "www.$DOMAIN"); fi
        certbot certonly --webroot -w /var/www/certbot \
          "${names[@]}" "${certbot_email[@]}" --agree-tos --non-interactive || true
      else
        warn "certbot is not installed, so no certificate could be requested."
        echo "  Install it and run ./install.sh again:"
        echo "      apt-get install -y certbot"
      fi
    fi

    if [ -f "$live" ]; then
      if write_nginx_site tls; then
        ok "HTTPS is on for $DOMAIN"
      else
        warn "The HTTPS configuration was rejected; the site stays on HTTP."
      fi
    else
      warn "No certificate yet — the site answers over HTTP only."
      DNS_VERDICT="${DNS_VERDICT:-No certificate was issued for $DOMAIN yet.}"
    fi
  fi
fi

# ── 6. What now ─────────────────────────────────────────────────────────────

echo
bold "AVERIX is running"
echo
if [ "$MODE" = "production" ]; then
  echo "  Site        https://$DOMAIN"
  echo "  Health      https://$DOMAIN/ready"
  echo
  if [ "$FRONT" = "nginx" ]; then
    echo "  Proxy       this server's own Nginx (AVERIX's Caddy stays off)"
    echo "  Renewal     certbot renew, which this server already runs on a timer"
  fi
  if [ -n "$DNS_VERDICT" ]; then
    echo
    warn "The site will show a certificate warning until this is fixed:"
    echo "    $DNS_VERDICT"
    if [ "$FRONT" = "nginx" ]; then
      echo "  Fix it, then run ./install.sh again to request the certificate."
    else
      echo "  Set the record at your domain registrar. Caddy retries on its own —"
      echo "  nothing here needs restarting once the record is correct."
    fi
  elif [ "$FRONT" = "caddy" ]; then
    echo
    echo "  The certificate is issued on the first request. If the site does not"
    echo "  load, check that ports 80 and 443 are open."
  fi
else
  echo "  Site        http://localhost:3000"
  echo "  API         http://localhost:8080/health"
fi
echo
echo "Next:"
echo "  1. Sign up on the site, then make yourself an administrator:"
echo "       $COMPOSE_SHOW exec api averixctl create-admin --email you@$DOMAIN"
echo "  2. In the admin panel, open Payments and enter the transfer details."
echo "  3. Turn on backups:"
echo "       (crontab -l 2>/dev/null; echo \"0 3 * * * cd $(pwd) && ./scripts/backup.sh >> /var/log/averix-backup.log 2>&1\") | crontab -"
echo
echo "Useful:"
echo "  $COMPOSE_SHOW ps"
echo "  $COMPOSE_SHOW logs -f api"
echo "  ./install.sh          # run again to deploy a new version"
echo
