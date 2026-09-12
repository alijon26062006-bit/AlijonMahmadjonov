-- 0008 contracts, milestones and the project workspace.
--
-- The contract is the source of truth for who may see what: workspace access,
-- file access, messaging and payment authorisation all resolve through
-- contract_participants. No endpoint checks "is this my project" by comparing
-- user ids by hand.

CREATE TABLE contracts (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  reference         text NOT NULL UNIQUE,
  project_id        uuid NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
  proposal_id       uuid REFERENCES proposals(id) ON DELETE SET NULL,
  client_id         uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  developer_id      uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,

  title             text NOT NULL,
  amount_minor      bigint NOT NULL CHECK (amount_minor > 0),
  currency          char(3) NOT NULL DEFAULT 'USD',
  -- Fee snapshot taken at signature, so a later schedule change is not retroactive.
  fee_percent       numeric(5,2) NOT NULL DEFAULT 0,
  fee_minor         bigint NOT NULL DEFAULT 0 CHECK (fee_minor >= 0),
  payout_minor      bigint NOT NULL CHECK (payout_minor >= 0),

  status            text NOT NULL DEFAULT 'active' CHECK (status IN
                      ('pending_funding','active','paused','submitted','completed',
                       'cancelled','disputed','closed')),
  -- Progress is derived from approved milestone value, written by the milestone
  -- trigger below so the workspace header never has to aggregate on read.
  progress_percent  int NOT NULL DEFAULT 0 CHECK (progress_percent BETWEEN 0 AND 100),
  released_minor    bigint NOT NULL DEFAULT 0 CHECK (released_minor >= 0),
  funded_minor      bigint NOT NULL DEFAULT 0 CHECK (funded_minor >= 0),

  starts_on         date,
  due_on            date,
  delivery_days     int,

  -- How the completed contract may be shown on the developer's public profile.
  -- The developer's own balance and earnings are never public regardless.
  price_visibility  text NOT NULL DEFAULT 'range' CHECK (price_visibility IN
                      ('public','range','hidden','private')),
  client_allows_showcase boolean NOT NULL DEFAULT true,

  completed_at      timestamptz,
  cancelled_at      timestamptz,
  cancelled_by      uuid REFERENCES users(id) ON DELETE SET NULL,
  cancellation_reason text,
  is_demo           boolean NOT NULL DEFAULT false,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT contracts_parties_differ CHECK (client_id <> developer_id),
  CONSTRAINT contracts_payout_matches CHECK (payout_minor + fee_minor = amount_minor)
);
CREATE INDEX contracts_client_idx  ON contracts (client_id, created_at DESC);
CREATE INDEX contracts_dev_idx     ON contracts (developer_id, created_at DESC);
CREATE INDEX contracts_project_idx ON contracts (project_id);
CREATE INDEX contracts_status_idx  ON contracts (status);
SELECT attach_touch_trigger('contracts');

-- Membership table. Admins are not listed here; their access comes from the
-- admin role and is written to the audit log on every use.
CREATE TABLE contract_participants (
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role        text NOT NULL CHECK (role IN ('client','developer','observer')),
  can_message boolean NOT NULL DEFAULT true,
  can_upload  boolean NOT NULL DEFAULT true,
  added_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  removed_at  timestamptz,
  PRIMARY KEY (contract_id, user_id)
);
CREATE INDEX contract_participants_user_idx ON contract_participants (user_id)
  WHERE removed_at IS NULL;

CREATE TABLE milestones (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id   uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  position      int NOT NULL CHECK (position >= 1),
  title         text NOT NULL,
  detail        text,
  amount_minor  bigint NOT NULL CHECK (amount_minor > 0),
  currency      char(3) NOT NULL DEFAULT 'USD',

  status        text NOT NULL DEFAULT 'draft' CHECK (status IN
                  ('draft','funded','in_progress','submitted','revision_requested',
                   'approved','released','disputed','cancelled')),
  due_on        date,
  revision_count int NOT NULL DEFAULT 0,
  -- Revision limit agreed in the proposal; exceeding it is a dispute, not a loop.
  revision_limit int NOT NULL DEFAULT 2,

  submitted_at  timestamptz,
  submission_note text,
  approved_at   timestamptz,
  approved_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  released_at   timestamptz,
  revision_note text,
  cancelled_at  timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX milestones_position_key ON milestones (contract_id, position);
CREATE INDEX milestones_status_idx ON milestones (contract_id, status);
SELECT attach_touch_trigger('milestones');

-- Every state change, with who made it. The workspace activity feed and any
-- dispute investigation read from here rather than guessing from timestamps.
CREATE TABLE milestone_events (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  milestone_id uuid NOT NULL REFERENCES milestones(id) ON DELETE CASCADE,
  actor_id     uuid REFERENCES users(id) ON DELETE SET NULL,
  from_status  text,
  to_status    text NOT NULL,
  note         text,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX milestone_events_milestone_idx ON milestone_events (milestone_id, created_at DESC);

-- What the developer hands over for a milestone.
CREATE TABLE deliverables (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id  uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  milestone_id uuid REFERENCES milestones(id) ON DELETE SET NULL,
  kind         text NOT NULL CHECK (kind IN ('file','link','repository','note')),
  title        text NOT NULL,
  detail       text,
  file_id      uuid,
  url          text,
  submitted_by uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  accepted_at  timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX deliverables_contract_idx ON deliverables (contract_id, created_at DESC);

-- Recomputes contract progress and released total from its milestones.
CREATE OR REPLACE FUNCTION contracts_refresh_progress() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  cid uuid := coalesce(NEW.contract_id, OLD.contract_id);
  total bigint;
  done  bigint;
  rel   bigint;
  fund  bigint;
BEGIN
  SELECT coalesce(sum(amount_minor), 0),
         coalesce(sum(amount_minor) FILTER (WHERE status IN ('approved','released')), 0),
         coalesce(sum(amount_minor) FILTER (WHERE status = 'released'), 0),
         coalesce(sum(amount_minor) FILTER (WHERE status <> 'draft' AND status <> 'cancelled'), 0)
    INTO total, done, rel, fund
    FROM milestones WHERE contract_id = cid;

  UPDATE contracts
     SET progress_percent = CASE WHEN total > 0 THEN least(100, round(done * 100.0 / total))::int
                                 ELSE progress_percent END,
         released_minor   = rel,
         funded_minor     = fund,
         updated_at       = now()
   WHERE id = cid;
  RETURN NULL;
END;
$$;
CREATE TRIGGER milestones_refresh_contract
  AFTER INSERT OR UPDATE OF status, amount_minor OR DELETE ON milestones
  FOR EACH ROW EXECUTE FUNCTION contracts_refresh_progress();
