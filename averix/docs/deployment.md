# Putting AVERIX on a server

One server, one command, HTTPS included.

```bash
git clone <this repository> /srv/averix && cd /srv/averix
./install.sh
```

That covers everything in the next three sections: Docker, the secrets, the
build, the migrations and the certificate. The rest of this page is what the
installer does, for when you want to do it yourself or something goes wrong.

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
backup script includes them. For more than one server, set `S3_DRIVER=s3` and
the `S3_*` values; any S3-compatible provider works.

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
