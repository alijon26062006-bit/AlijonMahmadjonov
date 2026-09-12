# AVERIX

A marketplace for software work: clients post projects, developers propose, and
the contract, the milestones, the messages and the money all live in one place.

This repository holds the whole product.

```
apps/web            Next.js front end (mobile first, 375px up)
services/api-go     Go API — the source of truth for every business action
services/ai-python  FastAPI analysis service — GitHub reading, drafting, matching aids
database/migrations Reversible SQL migrations, the schema's source of truth
brand/              Design tokens and the AVERIX mark
infrastructure/     Nginx and Docker configuration
docs/               How the parts that need explaining actually work
scripts/            Token build, reference-data sync, demo seed
```

## Running it locally

You need PostgreSQL 16, Redis 7, Go 1.25 and Node 22.

```bash
# 1. Database and cache
createdb averix
redis-server --port 6379 &

# 2. Configuration
cp .env.example .env          # then edit DATABASE_URL, REDIS_URL and the secrets

# 3. Schema
cd services/api-go && go run ./cmd/averixctl migrate

# 4. The API
go run ./cmd/api               # http://localhost:8080

# 5. The web app
cd ../../apps/web && npm install && npm run dev   # http://localhost:3000
```

The web app proxies `/api/v1` to the Go service, so the session cookie stays
first-party in development exactly as it is in production.

### Demo data

```bash
node scripts/seed-demo.mjs
```

Creates a client, two developers and an administrator, publishes projects and
portfolio work, sends proposals, signs a contract, funds a milestone through
the manual payment flow and leaves a conversation behind — all by driving the
real API, so nothing in it is fabricated. **Development only**: every record is
marked as demo data and the script refuses to touch a production database.

Accounts it creates all use the password `correct horse battery staple`:

| Role | Email |
| --- | --- |
| Client | nilufar@nurstore.example |
| Developer | alijon@example.dev |
| Developer | saida@example.dev |
| Administrator | ops@averix.example |

## Tests

```bash
cd services/api-go && go test ./...     # needs TEST_DATABASE_URL and TEST_REDIS_URL
cd services/ai-python && pytest -q
cd apps/web && npm run typecheck && npm run build
```

The Go suite runs against a real PostgreSQL and Redis — every migration,
authorisation rule and database trigger is exercised, not mocked.

## How it fits together

The Go service owns every decision that matters: authentication, authorisation,
projects, proposals, contracts, milestones, messages and payment orchestration.
The Python service analyses and drafts — GitHub repositories, project briefs,
technical summaries — and can never release money, change a role, ban a user or
approve a payment. Those are Go's, always.

Further reading:

- [`docs/payments.md`](docs/payments.md) — how money moves with no gateway
  connected: bank transfer plus an administrator's confirmation, on top of a
  provider abstraction ready for a real gateway.
- [`docs/external-content.md`](docs/external-content.md) — URL validation, SSRF
  defence, and the sandboxed in-app browser that previews a developer's live
  project without giving it access to AVERIX.

## Design

The design system is generated from `brand/tokens.json`:

```bash
node scripts/build-tokens.mjs    # writes apps/web/styles/tokens.css
```

Mobile first, from 375px up: comfortable touch targets, bottom navigation,
bottom sheets, sticky primary actions, skeletons instead of blank screens, and
light, dark and system themes throughout.
