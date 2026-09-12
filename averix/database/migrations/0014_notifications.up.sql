-- 0014 notifications.
--
-- One row per notification with a delivery row per channel, so an email that
-- bounced does not make the in-app copy disappear, and a channel can be added
-- without touching the notification itself.

CREATE TABLE notifications (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type        text NOT NULL CHECK (type IN (
                'proposal_received','proposal_accepted','proposal_declined','proposal_shortlisted',
                'project_invitation','project_published','project_recommended',
                'message_received',
                'milestone_submitted','milestone_revision_requested','milestone_approved','milestone_released',
                'payment_succeeded','payment_failed','payment_refunded',
                'review_received','review_published',
                'github_analysis_complete','github_analysis_failed',
                'contract_started','contract_completed','contract_cancelled',
                'dispute_opened','dispute_resolved',
                'account_verified','account_warning','account_suspended')),
  title       text NOT NULL,
  body        text,
  -- In-app destination. Always a relative path so a notification can never
  -- redirect a user off the platform.
  href        text CHECK (href IS NULL OR href ~ '^/'),
  actor_id    uuid REFERENCES users(id) ON DELETE SET NULL,
  -- Loose references; a deleted project should not delete the notification.
  project_id  uuid REFERENCES projects(id) ON DELETE SET NULL,
  contract_id uuid REFERENCES contracts(id) ON DELETE SET NULL,
  proposal_id uuid REFERENCES proposals(id) ON DELETE SET NULL,
  milestone_id uuid REFERENCES milestones(id) ON DELETE SET NULL,
  metadata    jsonb NOT NULL DEFAULT '{}'::jsonb,
  priority    text NOT NULL DEFAULT 'normal' CHECK (priority IN ('low','normal','high')),
  read_at     timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX notifications_user_idx   ON notifications (user_id, created_at DESC);
CREATE INDEX notifications_unread_idx ON notifications (user_id) WHERE read_at IS NULL;

CREATE TABLE notification_deliveries (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  notification_id uuid NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
  channel         text NOT NULL CHECK (channel IN ('in_app','email','push','webhook')),
  status          text NOT NULL DEFAULT 'queued'
                    CHECK (status IN ('queued','sent','delivered','failed','skipped','suppressed')),
  provider_ref    text,
  error           text,
  attempts        int NOT NULL DEFAULT 0,
  next_attempt_at timestamptz,
  sent_at         timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX notification_deliveries_key ON notification_deliveries (notification_id, channel);
CREATE INDEX notification_deliveries_pending_idx ON notification_deliveries (next_attempt_at)
  WHERE status IN ('queued','failed');
SELECT attach_touch_trigger('notification_deliveries');

-- Per-user, per-type channel preferences. A missing row means the default for
-- that type, so a new notification type does not require a backfill.
CREATE TABLE notification_preferences (
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type       text NOT NULL,
  in_app     boolean NOT NULL DEFAULT true,
  email      boolean NOT NULL DEFAULT true,
  push       boolean NOT NULL DEFAULT true,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, type)
);

-- Web-push subscriptions. Kept per device so revoking one does not silence all.
CREATE TABLE push_subscriptions (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  endpoint   text NOT NULL,
  p256dh     text NOT NULL,
  auth       text NOT NULL,
  user_agent text,
  failed_count int NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  last_used_at timestamptz
);
CREATE UNIQUE INDEX push_subscriptions_endpoint_key ON push_subscriptions (endpoint);
CREATE INDEX push_subscriptions_user_idx ON push_subscriptions (user_id);

-- Outbound email log, for support ("did they get it?") and bounce handling.
CREATE TABLE email_log (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid REFERENCES users(id) ON DELETE SET NULL,
  to_address  citext NOT NULL,
  template    text NOT NULL,
  subject     text NOT NULL,
  status      text NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued','sent','failed','bounced','complained')),
  provider_ref text,
  error       text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  sent_at     timestamptz
);
CREATE INDEX email_log_to_idx ON email_log (to_address, created_at DESC);
