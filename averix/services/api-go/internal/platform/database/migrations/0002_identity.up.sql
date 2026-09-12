-- 0002 identity: users, credentials, sessions, roles, verification.
--
-- One account, one or more roles. A person may eventually hold both CLIENT and
-- DEVELOPER — the roles table allows it while the interfaces stay separate,
-- because the active role is chosen per session rather than baked into the user.

CREATE TABLE users (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email               citext NOT NULL,
  email_verified_at   timestamptz,
  username            citext NOT NULL,
  -- bcrypt/argon2 hash. NULL when the account was created through OAuth only.
  password_hash       text,
  full_name           text NOT NULL CHECK (length(btrim(full_name)) BETWEEN 1 AND 120),
  headline            text CHECK (headline IS NULL OR length(headline) <= 120),
  locale              text NOT NULL DEFAULT 'en' CHECK (locale ~ '^[a-z]{2}(-[A-Z]{2})?$'),
  timezone            text NOT NULL DEFAULT 'UTC',
  country_code        char(2),
  city                text,
  -- 'active' | 'suspended' | 'deactivated' | 'pending' (registered, no role chosen yet)
  status              text NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','active','suspended','deactivated')),
  suspended_reason    text,
  suspended_until     timestamptz,
  identity_verified_at timestamptz,
  last_seen_at        timestamptz,
  -- Failed-login throttling lives on the row so it survives a cache flush.
  failed_login_count  int NOT NULL DEFAULT 0,
  locked_until        timestamptz,
  is_demo             boolean NOT NULL DEFAULT false,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  deleted_at          timestamptz
);
-- Uniqueness ignores soft-deleted rows so an address can be reused after erasure.
CREATE UNIQUE INDEX users_email_key    ON users (email)    WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX users_username_key ON users (username) WHERE deleted_at IS NULL;
CREATE INDEX users_username_trgm ON users USING gin (username gin_trgm_ops);
CREATE INDEX users_name_trgm     ON users USING gin (full_name gin_trgm_ops);
CREATE INDEX users_status_idx    ON users (status) WHERE deleted_at IS NULL;
CREATE INDEX users_demo_idx      ON users (is_demo) WHERE is_demo;
ALTER TABLE users ADD CONSTRAINT users_username_shape
  CHECK (username ~ '^[a-z0-9](?:[a-z0-9_-]{1,28}[a-z0-9])$');
SELECT attach_touch_trigger('users');

CREATE TABLE user_roles (
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role       text NOT NULL CHECK (role IN ('client','developer','admin','moderator')),
  granted_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, role)
);
CREATE INDEX user_roles_role_idx ON user_roles (role);

-- Opaque server-side sessions. The cookie carries only the selector; the
-- verifier is stored hashed, so a database leak does not hand over live sessions.
CREATE TABLE sessions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  selector        text NOT NULL UNIQUE,
  verifier_hash   bytea NOT NULL,
  -- Which interface this session is operating in; a user with both roles has
  -- one session per mode rather than a role-switch that leaks across tabs.
  active_role     text NOT NULL CHECK (active_role IN ('client','developer','admin','moderator')),
  user_agent      text,
  ip              inet,
  -- CSRF double-submit token, rotated with the session.
  csrf_token      text NOT NULL,
  expires_at      timestamptz NOT NULL,
  revoked_at      timestamptz,
  last_used_at    timestamptz NOT NULL DEFAULT now(),
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX sessions_user_idx    ON sessions (user_id) WHERE revoked_at IS NULL;
CREATE INDEX sessions_expires_idx ON sessions (expires_at) WHERE revoked_at IS NULL;

-- Single-use tokens for email verification, password reset and project invites.
CREATE TABLE auth_tokens (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid REFERENCES users(id) ON DELETE CASCADE,
  purpose     text NOT NULL CHECK (purpose IN ('email_verify','password_reset','email_change','invite')),
  token_hash  bytea NOT NULL,
  payload     jsonb NOT NULL DEFAULT '{}'::jsonb,
  expires_at  timestamptz NOT NULL,
  consumed_at timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX auth_tokens_hash_key ON auth_tokens (token_hash);
CREATE INDEX auth_tokens_user_purpose_idx ON auth_tokens (user_id, purpose) WHERE consumed_at IS NULL;

-- OAuth handshake state. Persisted rather than held in a cookie so the callback
-- can be validated even when the browser drops the cookie on a cross-site redirect.
CREATE TABLE oauth_states (
  state         text PRIMARY KEY,
  provider      text NOT NULL CHECK (provider IN ('github')),
  user_id       uuid REFERENCES users(id) ON DELETE CASCADE,
  -- PKCE verifier and the post-login destination, validated on return.
  code_verifier text,
  redirect_to   text,
  scopes        text[] NOT NULL DEFAULT '{}',
  expires_at    timestamptz NOT NULL,
  consumed_at   timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX oauth_states_expires_idx ON oauth_states (expires_at);

-- Rate limiting has a Redis fast path; this table is the durable ledger used for
-- brute-force lockouts and abuse reports, which must survive a cache restart.
CREATE TABLE rate_limit_events (
  id         bigserial PRIMARY KEY,
  bucket     text NOT NULL,
  subject    text NOT NULL,
  ip         inet,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX rate_limit_events_lookup_idx ON rate_limit_events (bucket, subject, created_at DESC);
