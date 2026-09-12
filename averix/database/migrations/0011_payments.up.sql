-- 0011 payments.
--
-- AVERIX orchestrates payments through a provider abstraction; it does not hold
-- funds itself and makes no escrow claim. `payment_intents` is the platform's
-- own ledger of what it asked a provider to do, `payment_transactions` is what
-- the provider reported back. Reconciliation compares the two.

CREATE TABLE payment_providers (
  code          text PRIMARY KEY,
  display_name  text NOT NULL,
  -- Whether credentials are present in this environment. The UI shows a
  -- configuration state rather than a dead button when this is false.
  is_configured boolean NOT NULL DEFAULT false,
  is_enabled    boolean NOT NULL DEFAULT false,
  -- Capability flags drive what the product offers: a provider without
  -- 'hold' support must not be described to users as escrow.
  capabilities  text[] NOT NULL DEFAULT '{}',
  supported_currencies char(3)[] NOT NULL DEFAULT '{}',
  config_note   text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
SELECT attach_touch_trigger('payment_providers');

INSERT INTO payment_providers (code, display_name, capabilities, supported_currencies, config_note) VALUES
  ('manual',  'Manual bank transfer', '{charge,refund,payout}',              '{USD,EUR}',
   'Always available. An administrator records the transfer; nothing is held by AVERIX.'),
  ('stripe',  'Stripe',               '{charge,refund,payout,hold,webhook}', '{USD,EUR,GBP}',
   'Set STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET to enable.'),
  ('paddle',  'Paddle',               '{charge,refund,webhook}',             '{USD,EUR}',
   'Set PADDLE_API_KEY and PADDLE_WEBHOOK_SECRET to enable.');

CREATE TABLE payment_intents (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  reference       text NOT NULL UNIQUE,
  contract_id     uuid REFERENCES contracts(id) ON DELETE RESTRICT,
  milestone_id    uuid REFERENCES milestones(id) ON DELETE RESTRICT,
  payer_id        uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  payee_id        uuid REFERENCES users(id) ON DELETE RESTRICT,
  provider_code   text NOT NULL REFERENCES payment_providers(code) ON DELETE RESTRICT,

  direction       text NOT NULL CHECK (direction IN ('charge','payout','refund')),
  amount_minor    bigint NOT NULL CHECK (amount_minor > 0),
  fee_minor       bigint NOT NULL DEFAULT 0 CHECK (fee_minor >= 0),
  currency        char(3) NOT NULL,

  status          text NOT NULL DEFAULT 'created' CHECK (status IN
                    ('created','requires_action','processing','held','succeeded',
                     'failed','cancelled','refunded','partially_refunded')),
  -- The caller's idempotency key. A retried request returns the original intent
  -- instead of charging twice.
  idempotency_key text NOT NULL,
  provider_ref    text,
  provider_status text,
  failure_code    text,
  failure_message text,
  -- Opaque provider payload, redacted of anything secret before it is stored.
  provider_meta   jsonb NOT NULL DEFAULT '{}'::jsonb,
  authorised_at   timestamptz,
  captured_at     timestamptz,
  released_at     timestamptz,
  refunded_minor  bigint NOT NULL DEFAULT 0 CHECK (refunded_minor >= 0),
  is_demo         boolean NOT NULL DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT payment_intents_refund_bounds CHECK (refunded_minor <= amount_minor)
);
CREATE UNIQUE INDEX payment_intents_idempotency_key ON payment_intents (provider_code, idempotency_key);
CREATE UNIQUE INDEX payment_intents_provider_ref_key ON payment_intents (provider_code, provider_ref)
  WHERE provider_ref IS NOT NULL;
CREATE INDEX payment_intents_contract_idx ON payment_intents (contract_id, created_at DESC);
CREATE INDEX payment_intents_payer_idx    ON payment_intents (payer_id, created_at DESC);
CREATE INDEX payment_intents_status_idx   ON payment_intents (status)
  WHERE status IN ('created','requires_action','processing','held');
SELECT attach_touch_trigger('payment_intents');

-- Immutable: every provider-reported movement is appended, never updated.
CREATE TABLE payment_transactions (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  intent_id      uuid NOT NULL REFERENCES payment_intents(id) ON DELETE CASCADE,
  kind           text NOT NULL CHECK (kind IN
                   ('authorisation','capture','release','refund','chargeback','fee','payout','adjustment')),
  amount_minor   bigint NOT NULL,
  currency       char(3) NOT NULL,
  provider_ref   text,
  provider_event_id text,
  occurred_at    timestamptz NOT NULL DEFAULT now(),
  raw            jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX payment_transactions_intent_idx ON payment_transactions (intent_id, occurred_at);
CREATE UNIQUE INDEX payment_transactions_event_key ON payment_transactions (provider_event_id)
  WHERE provider_event_id IS NOT NULL;

-- Every webhook delivery, verified before it is trusted and recorded before it
-- is acted on, so a replay is a no-op and a signature failure is investigable.
CREATE TABLE payment_webhook_events (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider_code  text NOT NULL REFERENCES payment_providers(code) ON DELETE RESTRICT,
  provider_event_id text,
  event_type     text,
  signature_valid boolean NOT NULL,
  signature_detail text,
  payload        jsonb NOT NULL,
  processed_at   timestamptz,
  process_error  text,
  received_at    timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX payment_webhook_events_key ON payment_webhook_events (provider_code, provider_event_id)
  WHERE provider_event_id IS NOT NULL;
CREATE INDEX payment_webhook_events_unprocessed_idx ON payment_webhook_events (received_at)
  WHERE processed_at IS NULL;

-- Platform fee schedule. Versioned, and the applied percentage is snapshotted
-- onto the contract, so changing this never rewrites a signed deal.
CREATE TABLE fee_schedules (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name           text NOT NULL,
  -- Applies to contracts at or above this value; the highest matching band wins.
  from_minor     bigint NOT NULL DEFAULT 0,
  percent        numeric(5,2) NOT NULL CHECK (percent >= 0 AND percent <= 50),
  flat_minor     bigint NOT NULL DEFAULT 0 CHECK (flat_minor >= 0),
  currency       char(3) NOT NULL DEFAULT 'USD',
  side           text NOT NULL DEFAULT 'developer' CHECK (side IN ('developer','client','split')),
  is_active      boolean NOT NULL DEFAULT true,
  effective_from timestamptz NOT NULL DEFAULT now(),
  created_by     uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX fee_schedules_band_idx ON fee_schedules (currency, from_minor DESC) WHERE is_active;

INSERT INTO fee_schedules (name, from_minor, percent, currency, side) VALUES
  ('Standard',        0,       10.00, 'USD', 'developer'),
  ('Above $2,000',    200000,   8.00, 'USD', 'developer'),
  ('Above $10,000',   1000000,  6.00, 'USD', 'developer');

-- Developer-visible balance ledger. Private by construction: no endpoint
-- serialises this to anyone but the owner and an admin.
CREATE TABLE ledger_entries (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  intent_id    uuid REFERENCES payment_intents(id) ON DELETE SET NULL,
  contract_id  uuid REFERENCES contracts(id) ON DELETE SET NULL,
  kind         text NOT NULL CHECK (kind IN
                 ('earning','fee','payout','refund','adjustment','bonus')),
  amount_minor bigint NOT NULL,
  currency     char(3) NOT NULL,
  balance_after_minor bigint NOT NULL,
  description  text,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ledger_entries_user_idx ON ledger_entries (user_id, created_at DESC);
