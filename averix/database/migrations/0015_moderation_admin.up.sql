-- 0015 moderation, disputes, audit, platform settings.

CREATE TABLE reports (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  reporter_id  uuid REFERENCES users(id) ON DELETE SET NULL,
  -- What is being reported. Kept as (type, id) rather than nine nullable FKs.
  subject_type text NOT NULL CHECK (subject_type IN
                 ('user','project','proposal','portfolio_project','service','review','message')),
  subject_id   uuid NOT NULL,
  reason       text NOT NULL CHECK (reason IN
                 ('spam','fraud','off_platform_payment','plagiarism','abuse',
                  'misleading','nsfw','impersonation','security','other')),
  detail       text,
  status       text NOT NULL DEFAULT 'open'
                 CHECK (status IN ('open','reviewing','actioned','dismissed')),
  assigned_to  uuid REFERENCES users(id) ON DELETE SET NULL,
  resolution   text,
  resolved_at  timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX reports_status_idx  ON reports (status, created_at DESC);
CREATE INDEX reports_subject_idx ON reports (subject_type, subject_id);
SELECT attach_touch_trigger('reports');

CREATE TABLE moderation_queue (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_type text NOT NULL CHECK (subject_type IN
                 ('project','developer_profile','portfolio_project','service','review','photo')),
  subject_id   uuid NOT NULL,
  reason       text NOT NULL,
  -- 'automatic' entries come from content heuristics; 'report' from a user.
  origin       text NOT NULL DEFAULT 'automatic' CHECK (origin IN ('automatic','report','admin')),
  priority     int NOT NULL DEFAULT 50,
  status       text NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending','approved','rejected','escalated')),
  reviewed_by  uuid REFERENCES users(id) ON DELETE SET NULL,
  review_note  text,
  reviewed_at  timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX moderation_queue_pending_key ON moderation_queue (subject_type, subject_id)
  WHERE status = 'pending';
CREATE INDEX moderation_queue_open_idx ON moderation_queue (priority DESC, created_at)
  WHERE status = 'pending';

CREATE TABLE disputes (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  reference     text NOT NULL UNIQUE,
  contract_id   uuid NOT NULL REFERENCES contracts(id) ON DELETE RESTRICT,
  milestone_id  uuid REFERENCES milestones(id) ON DELETE SET NULL,
  opened_by     uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  against_id    uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  reason        text NOT NULL CHECK (reason IN
                  ('not_delivered','quality','scope','deadline','payment','communication','other')),
  claim         text NOT NULL,
  amount_minor  bigint CHECK (amount_minor IS NULL OR amount_minor >= 0),
  currency      char(3),
  status        text NOT NULL DEFAULT 'open' CHECK (status IN
                  ('open','awaiting_response','under_review','resolved','withdrawn','escalated')),
  -- Set only by an admin; the resolution and who made it are both recorded.
  outcome       text CHECK (outcome IS NULL OR outcome IN
                  ('client_favoured','developer_favoured','split','no_action','cancelled')),
  outcome_note  text,
  refund_minor  bigint CHECK (refund_minor IS NULL OR refund_minor >= 0),
  release_minor bigint CHECK (release_minor IS NULL OR release_minor >= 0),
  assigned_to   uuid REFERENCES users(id) ON DELETE SET NULL,
  response_due_at timestamptz,
  resolved_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  resolved_at   timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX disputes_status_idx   ON disputes (status, created_at DESC);
CREATE INDEX disputes_contract_idx ON disputes (contract_id);
SELECT attach_touch_trigger('disputes');

CREATE TABLE dispute_messages (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dispute_id  uuid NOT NULL REFERENCES disputes(id) ON DELETE CASCADE,
  author_id   uuid REFERENCES users(id) ON DELETE SET NULL,
  -- An admin note is visible only to staff.
  visibility  text NOT NULL DEFAULT 'parties'
                CHECK (visibility IN ('parties','admin_only')),
  body        text NOT NULL,
  file_id     uuid REFERENCES files(id) ON DELETE SET NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX dispute_messages_dispute_idx ON dispute_messages (dispute_id, created_at);

-- Append-only audit trail. Every privileged read and every state change that
-- touches money, roles or account status writes here.
CREATE TABLE audit_logs (
  id            bigserial PRIMARY KEY,
  actor_id      uuid REFERENCES users(id) ON DELETE SET NULL,
  actor_role    text,
  -- 'developer.suspend', 'payment.release', 'contract.view_as_admin', ...
  action        text NOT NULL,
  subject_type  text,
  subject_id    uuid,
  -- Before/after for state changes, redacted of secrets.
  before        jsonb,
  after         jsonb,
  ip            inet,
  user_agent    text,
  request_id    text,
  outcome       text NOT NULL DEFAULT 'success' CHECK (outcome IN ('success','denied','error')),
  detail        text,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_logs_actor_idx   ON audit_logs (actor_id, created_at DESC);
CREATE INDEX audit_logs_subject_idx ON audit_logs (subject_type, subject_id, created_at DESC);
CREATE INDEX audit_logs_action_idx  ON audit_logs (action, created_at DESC);

-- Admin actions against users, separate from audit_logs because these are
-- shown to the affected user and carry an expiry.
CREATE TABLE admin_actions (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  admin_id    uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  target_user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  action      text NOT NULL CHECK (action IN
                ('warn','suspend','unsuspend','verify_identity','unverify_identity',
                 'feature','unfeature','hide_content','restore_content','grant_role','revoke_role',
                 'force_password_reset','delete_account')),
  reason      text NOT NULL,
  detail      jsonb NOT NULL DEFAULT '{}'::jsonb,
  expires_at  timestamptz,
  reverted_at timestamptz,
  reverted_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX admin_actions_target_idx ON admin_actions (target_user_id, created_at DESC);
CREATE INDEX admin_actions_admin_idx  ON admin_actions (admin_id, created_at DESC);

-- Runtime settings an administrator may change without a deploy.
CREATE TABLE platform_settings (
  key         text PRIMARY KEY,
  value       jsonb NOT NULL,
  description text,
  -- 'public' settings are served to the web app; 'private' never leave the API.
  scope       text NOT NULL DEFAULT 'private' CHECK (scope IN ('public','private')),
  updated_by  uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
SELECT attach_touch_trigger('platform_settings');

INSERT INTO platform_settings (key, value, description, scope) VALUES
  ('proposals.max_per_day',        '10'::jsonb,    'Proposals a developer may submit per rolling day.', 'private'),
  ('proposals.min_cover_letter',   '120'::jsonb,   'Minimum cover-letter length in characters.', 'public'),
  ('projects.max_open_per_client', '15'::jsonb,    'Open projects a single client may hold.', 'private'),
  ('feed.threshold_override',      'null'::jsonb,  'Overrides the active weight set''s feed threshold when set.', 'private'),
  ('preview.enabled',              'true'::jsonb,  'Enables the in-app project preview browser.', 'public'),
  ('uploads.max_image_bytes',      '10485760'::jsonb, 'Maximum accepted image upload (10 MiB).', 'public'),
  ('uploads.max_file_bytes',       '52428800'::jsonb, 'Maximum accepted attachment (50 MiB).', 'public');

CREATE TABLE feature_flags (
  key          text PRIMARY KEY,
  description  text,
  is_enabled   boolean NOT NULL DEFAULT false,
  -- 0-100 rollout by stable hash of the user id.
  rollout_percent int NOT NULL DEFAULT 0 CHECK (rollout_percent BETWEEN 0 AND 100),
  enabled_for_roles text[] NOT NULL DEFAULT '{}',
  enabled_for_users uuid[] NOT NULL DEFAULT '{}',
  updated_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
SELECT attach_touch_trigger('feature_flags');

INSERT INTO feature_flags (key, description, is_enabled, rollout_percent) VALUES
  ('ai_project_assistant', 'Conversational project brief wizard for clients.', true, 100),
  ('github_analysis',      'GitHub repository analysis and technical profile.', true, 100),
  ('embedded_preview',     'In-app sandboxed browser for portfolio project URLs.', true, 100),
  ('services',             'Fixed-price developer services.', true, 100),
  ('web_push',             'Browser push notifications.', false, 0);

-- Background jobs. A real queue (Redis) drives execution; this table is the
-- durable record so a restart does not lose work and the admin panel can show
-- failures with their error.
CREATE TABLE jobs (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind          text NOT NULL,
  payload       jsonb NOT NULL DEFAULT '{}'::jsonb,
  -- Deduplicates enqueues, e.g. one GitHub sync per account in flight.
  dedupe_key    text,
  status        text NOT NULL DEFAULT 'queued'
                  CHECK (status IN ('queued','running','succeeded','failed','dead','cancelled')),
  attempts      int NOT NULL DEFAULT 0,
  max_attempts  int NOT NULL DEFAULT 5,
  run_after     timestamptz NOT NULL DEFAULT now(),
  locked_by     text,
  locked_at     timestamptz,
  last_error    text,
  finished_at   timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX jobs_dedupe_key ON jobs (kind, dedupe_key)
  WHERE dedupe_key IS NOT NULL AND status IN ('queued','running');
CREATE INDEX jobs_claimable_idx ON jobs (run_after) WHERE status = 'queued';
CREATE INDEX jobs_status_idx ON jobs (status, created_at DESC);
SELECT attach_touch_trigger('jobs');
