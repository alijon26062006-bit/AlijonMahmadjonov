# AVERIX

Биржа удалённой работы на русском языке: заказчик размещает заказ или покупает
готовую услугу, исполнитель откликается, а сделка, этапы, переписка и деньги
живут в одном месте.

Площадка не только для программистов. Восемь направлений: дизайн, разработка
и IT, тексты и переводы, SEO, SMM и маркетинг, аудио и видео, бизнес-услуги,
обучение — 31 профессия, 117 категорий и 171 навык, по которым заказ находит
исполнителя.

Продаются два разных способа купить работу, и оба доведены до конца:

- **Заказ** — вы описываете задачу, исполнители присылают отклики с ценой,
  сроком и подходом, вы выбираете и заключаете сделку.
- **Услуга** — готовое предложение с фиксированной ценой и сроком: выбрали
  пакет, описали задачу, сделка открылась сразу, без переговоров.

Этот репозиторий содержит продукт целиком.

```
apps/web            Next.js front end (mobile first, 375px up)
services/api-go     Go API — the source of truth for every business action
services/ai-python  FastAPI analysis service — GitHub reading, drafting, matching aids
database/migrations Reversible SQL migrations, the schema's source of truth
brand/              Design tokens and the AVERIX mark
infrastructure/     Nginx and Docker configuration
docs/               How the parts that need explaining actually work
scripts/            Token build, reference-data sync, demo seed, browser smoke tests
```

## Running it locally

With Docker, one command:

```bash
./install.sh --dev        # http://localhost:3000
node scripts/seed-demo.mjs
```

Or without Docker, if you want the services in your own terminal — you need
PostgreSQL 16, Redis 7, Go 1.25 and Node 22.

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

Создаёт заказчика, двух исполнителей (разработчика и дизайнера) и
администратора, публикует заказы в разных направлениях и работы в портфолио,
отправляет отклики, заключает сделку, проводит оплату этапа через ручной
перевод и оставляет переписку — всё через настоящий API, поэтому ничего в этих
данных не нарисовано. **Только для разработки**: сценарий отказывается
работать с производственной базой.

Все аккаунты используют пароль `правильная лошадь батарейка скрепка`:

| Роль | Почта |
| --- | --- |
| Заказчик | nilufar@nurstore.example |
| Исполнитель (разработка) | alijon@example.dev |
| Исполнитель (дизайн) | saida@example.dev |
| Администратор | ops@averix.example |

## Putting it on a server

On a bare Ubuntu server whose DNS already points at it:

```bash
git clone <this repository> /srv/averix && cd /srv/averix
./install.sh
```

That is the whole thing. It installs Docker if the machine lacks it, generates
the secrets, writes `.env` for **averix.dev**, builds the images, applies every
migration, starts the stack and waits until the site answers. Caddy gets the
HTTPS certificate itself. Running it again is how you deploy a new version —
existing secrets are kept.

```bash
./install.sh --domain averix.dev --email you@averix.dev   # a different domain
./install.sh --dev                                        # localhost, no certificate
make help                                                 # the day-to-day commands
```

The full procedure — backups, the first administrator, what to do when
something is wrong — is in [`docs/deployment.md`](docs/deployment.md).

## Tests

```bash
cd services/api-go && go test ./...     # needs TEST_DATABASE_URL and TEST_REDIS_URL
cd services/ai-python && pytest -q
cd apps/web && npm run typecheck && npm run build
```

The Go suite runs against a real PostgreSQL and Redis — every migration,
authorisation rule and database trigger is exercised, not mocked.

Сквозная проверка в настоящем браузере, по живому стеку:

```bash
AVERIX_SMOKE_URL=http://localhost:3000 node scripts/smoke.mjs
AVERIX_SMOKE_URL=http://localhost:3000 node scripts/smoke-services.mjs
```

Первый сценарий проходит путь «регистрация → анкета из девяти шагов →
публикация → заказ → отклик → наём → сделка» с двух сторон. Второй —
«услуга → покупка в один шаг» и все экраны администратора. Юнит-тесты
проверяют модули; эти два отвечают на вопрос, может ли человек довести дело
до конца, не открывая консоль.

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
