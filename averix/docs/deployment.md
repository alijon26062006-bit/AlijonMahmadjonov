# Putting AVERIX on a server

One server, one command, HTTPS included.

```bash
git clone <this repository> /srv/averix && cd /srv/averix
./install.sh
```

That covers everything in the next three sections: Docker, the secrets, the
build, the migrations and the certificate. The rest of this page is what the
installer does, for when you want to do it yourself or something goes wrong.


## Email: what breaks without it

Confirming an address is not decoration. Publishing a profile, publishing a
project and changing an email all require a confirmed address, and the
confirmation arrives by email. On a deployment with no SMTP server configured,
that link is never sent, so nobody except the operator can publish anything —
and the platform looks broken while behaving exactly as designed.

Set these in `.env` and run `./install.sh` again:

```
SMTP_HOST=smtp.example.com
SMTP_PORT=587            # 465 also works; the client picks STARTTLS or TLS
SMTP_USERNAME=no-reply@averix.dev
SMTP_PASSWORD=…
MAIL_FROM_ADDRESS=no-reply@averix.dev
MAIL_FROM_NAME=AVERIX
```

Nothing is silently dropped while mail is unconfigured: every message is still
written to `email_log` with the status `failed` and the reason
`smtp_not_configured`, so the record of what should have been sent survives.

Until the mail server is there, an address can be confirmed from the server:

```bash
docker compose -f docker-compose.production.yml exec api \
  averixctl verify-email --email someone@example.com
```

This is an operator's act, recorded in the audit log like every other. It
grants nothing new — whoever can run it already has the database.

## What you need

- A server with **2 CPU, 4 GB RAM, 40 GB SSD** and Ubuntu 22.04 or 24.04.
  Hetzner CX22, DigitalOcean 4 GB, Contabo VPS S — any of them is enough for
  the first few thousand users.
- A **domain** whose A record points at the server's IP address. Set this
  first: the certificate is issued by proving you control the domain, and
  DNS takes a few minutes to propagate.
- **Docker**. On a fresh server:

```bash
curl -fsSL https://get.docker.com | sh
```

## 1. Get the code onto the server

```bash
ssh root@YOUR-SERVER-IP

mkdir -p /srv && cd /srv
git clone https://github.com/YOUR-ACCOUNT/YOUR-REPO.git averix
cd averix
```

## 2. Configure it (the installer does this for you)

```bash
cp .env.example .env

# Three secrets, each a fresh random value. Never reuse one for another.
echo "COOKIE_SECRET=$(openssl rand -hex 32)"        >> .env
echo "DATA_ENCRYPTION_KEY=$(openssl rand -hex 32)"  >> .env
echo "AI_SERVICE_TOKEN=$(openssl rand -hex 32)"     >> .env
echo "POSTGRES_PASSWORD=$(openssl rand -hex 24)"    >> .env

nano .env
```

In the editor, set these four and save:

```
AVERIX_DOMAIN=averix.dev          # your domain, no https://
ACME_EMAIL=you@example.com            # certificate expiry warnings go here
APP_URL=https://averix.dev
API_URL=https://averix.dev
```

Then delete the placeholder lines that `openssl` replaced (the ones still
reading `replace-with-…`), so each value appears once.

> **DATA_ENCRYPTION_KEY is permanent.** It encrypts stored GitHub tokens.
> Changing it later makes them unreadable. COOKIE_SECRET can be rotated —
> everyone is simply signed out.

## 3. Start it (the installer does this for you)

```bash
docker compose -f docker-compose.production.yml up -d --build
```

The first build takes a few minutes. In order, it will: start PostgreSQL and
Redis, **apply every migration** (you never create a table by hand), start the
API, the worker, the analysis service and the web app, then start Caddy, which
requests your certificate.

Watch it come up:

```bash
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml logs -f caddy
```

Open `https://your-domain` — the certificate is already valid.

## 3b. A server that already runs Nginx

Plenty of servers already have Nginx on ports 80 and 443 — a hosting panel,
another site. Stopping it to make room for AVERIX's own proxy would take those
down, so the installer does not: when something else is already listening, it
puts AVERIX behind it instead.

```bash
./install.sh --behind-nginx     # or just ./install.sh — it notices on its own
```

What changes:

- Caddy is scaled to zero. The stack's definition is unchanged; dropping the
  overlay from the command line brings it back.
- The API and the web application publish on the loopback interface only.
  Nginx on the same host reaches them; nothing else on the network does — the
  same exposure they had behind Caddy. The port numbers are chosen at install
  time and recorded in `.env` as `AVERIX_WEB_HOST_PORT` and
  `AVERIX_API_HOST_PORT`: a server that already runs Nginx usually runs other
  things too, and 3000 and 8080 are the first ports anything takes. Binding
  them blindly either fails or, worse, succeeds while Nginx ends up pointed at
  somebody else's container — so before writing the site, the installer checks
  that the port really answers with AVERIX and stops if it does not.
- A site file is written to whichever of `sites-available` or `conf.d` this
  Nginx actually includes, and `nginx -t` has to pass before anything is
  reloaded. If it does not, the file is removed again.
- The certificate comes from `certbot certonly --webroot`, which does not edit
  your Nginx configuration. Install certbot first (`apt-get install -y
  certbot`) or the site stays on plain HTTP until you do.

The site is written in two passes — plain HTTP, then HTTPS once the
certificate exists — because a server block naming a certificate file that is
not there yet fails `nginx -t`, and the certificate cannot be issued until
Nginx is answering the challenge on port 80. Re-running is safe: an existing
certificate skips straight to the second pass.

Force the stack's own proxy instead with `--with-caddy`, which is the right
choice on a server with nothing else on those ports.

## 4. Check it is healthy

```bash
curl https://your-domain/health     # the process is alive
curl https://your-domain/ready      # database, cache, storage and worker
```

`/ready` reports each dependency by name, and never leaks a connection string
or a secret. Point your uptime monitor at it.

## 5. Make yourself an administrator

The first administrator is created by the operator, on the server. There is
deliberately no way to promote yourself from inside the product.

```bash
# Sign up through the site first, then:
docker compose -f docker-compose.production.yml exec api \
  averixctl create-admin --email you@example.com
```

Then, in the admin panel, open **Payments → transfer details** and enter the
bank account clients should send money to. Until you do, funding a milestone
answers "payments aren't set up on this platform yet" — it never asks anyone
to send money nowhere.

## 5b. Who may see identity documents

Nobody, until you say so — not even you. The two permissions that open a
passport photograph (`identity_verification.view` and
`identity_verification.review`) are granted to one account at a time from
**Пользователи → the person → Именные разрешения**, and revoking one takes
effect on that person's next request. On top of the grant, opening the section
asks the reviewer for their password again, for ten minutes.

Raw images are deleted `identity.retention_days` days after the decision (180
by default); the decision, its reason and the log of who looked survive. The
worker does this hourly — if you run the API without the worker, nothing is
ever purged.

Full details, and what is deliberately impossible, in
[identity-verification.md](identity-verification.md).

## 6. Turn on backups

```bash
crontab -e
```

```
0 3 * * * cd /srv/averix && ./scripts/backup.sh >> /var/log/averix-backup.log 2>&1
```

That dumps the database and the uploads to `/var/backups/averix`, keeps
fourteen days, and **reads the dump back** to prove it is not an empty file.

Copy them off the server as well — a backup that lives only on the machine it
backs up is not a backup:

```bash
# From your own computer, nightly
rsync -az root@YOUR-SERVER-IP:/var/backups/averix/ ~/averix-backups/
```

Restoring, when you need it:

```bash
./scripts/restore.sh /var/backups/averix/averix-db-20260101-030000.dump
```

**Test the restore on a spare server before you need it.** A backup nobody has
restored is a hope.

## Deploying a new version

```bash
cd /srv/averix
git pull
docker compose -f docker-compose.production.yml up -d --build
```

Migrations run before the new API starts. The old containers keep serving
until the new ones are healthy, and in-flight requests are drained rather than
cut.

## What runs where

| Container | Port | Reachable from |
| --- | --- | --- |
| caddy | 80, 443 | the internet |
| web | 3000 | caddy only |
| api | 8080 | caddy only |
| ai | 8000 | api only — and it still requires the shared token |
| postgres | 5432 | api and worker only |
| redis | 6379 | api and worker only |

Only Caddy publishes a port. The database is not exposed to the internet at
all, which is worth checking after any change:

```bash
docker compose -f docker-compose.production.yml ps --format 'table {{.Service}}\t{{.Ports}}'
```

## Optional pieces

Each of these is genuinely optional: the product runs without it and says so
where it matters, rather than showing a button that does nothing.

**Email** — set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`.
Without it, verification tokens are issued and written to the log instead of
being sent.

**GitHub** — create an OAuth App with the callback
`https://your-domain/api/v1/github/callback`, then set `GITHUB_CLIENT_ID` and
`GITHUB_CLIENT_SECRET`.

**AI analysis** — set `AI_API_KEY`. Without it, technologies are still detected
deterministically from manifests, and every generated field reports that it
was not generated.

**Object storage** — with one server, uploads live in a Docker volume and the
backup script includes them. `STORAGE_ROOT` must be an absolute path — the
compose file mounts the volume at `/data/storage` and the API refuses to start
in production with a relative one, because a relative path writes inside the
container and every upload would disappear on the next deployment. For more
than one server, set `S3_DRIVER=s3` and the `S3_*` values; any S3-compatible
provider works.

**A staff chat** — set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` and the
staff chat gets one line and a link when something needs a person. It never
receives documents, at any setting: see
[identity-verification.md](identity-verification.md).

**A payment gateway** — `PAYMENTS_DEFAULT_PROVIDER=manual` means bank transfer
confirmed by an administrator, which needs no gateway at all. See
[payments.md](payments.md).

## When something is wrong

```bash
# What is running, and is anything restarting in a loop?
docker compose -f docker-compose.production.yml ps

# Logs, last hour, one service
docker compose -f docker-compose.production.yml logs --since 1h api

# Which dependency is unhappy
curl -s https://your-domain/ready | jq

# Database console
docker compose -f docker-compose.production.yml exec postgres \
  psql -U averix -d averix

# Migration state
docker compose -f docker-compose.production.yml exec api averixctl migrate status
```

**The certificate did not issue.** Caddy needs port 80 reachable from the
internet and the A record already pointing here. Check with
`dig +short your-domain` and `docker compose logs caddy`.

**The build fails with `i/o timeout` fetching a dependency.** DNS works on
the host but not inside containers — common on VPS images whose provider
resolver ignores NAT'd traffic. `./install.sh` detects and fixes this now; by
hand it is:

```bash
cat > /etc/docker/daemon.json <<'JSON'
{ "dns": ["1.1.1.1", "8.8.8.8"] }
JSON
systemctl restart docker
```

If it still fails, a firewall is dropping forwarded traffic:
`iptables -P FORWARD ACCEPT`, or with ufw, `ufw default allow routed`.

**The API restarts in a loop.** Almost always a missing or too-short secret —
it refuses to start rather than falling back to a default.
`docker compose logs api` names the variable.

**Uploads fail in production but worked locally.** Check `MAX_FILE_BYTES` and,
if you put Nginx in front instead of Caddy, `client_max_body_size`.

## Scaling later, briefly

This stack is one server on purpose. When it is not enough:

1. Move PostgreSQL to a managed database and point `DATABASE_URL` at it.
2. Move uploads to S3 (`S3_DRIVER=s3`).
3. Run several `api` and `web` containers behind the same proxy.
4. Relay realtime events between the API instances through Redis pub/sub —
   the hub is per process today, which is the one thing that needs code before
   a second API container is added.
