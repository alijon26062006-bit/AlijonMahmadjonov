-- 0007 proposals and the matching engine's persisted output.
--
-- A proposal is a substantive document, not a message. The NOT NULL columns are
-- the product decision that "ready to do it" cannot be submitted.

CREATE TABLE proposals (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id        uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  developer_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,

  amount_minor      bigint NOT NULL CHECK (amount_minor > 0),
  currency          char(3) NOT NULL DEFAULT 'USD',
  -- What the developer is paid vs what the client pays; the platform fee sits
  -- between them and is resolved from the fee schedule at accept time.
  fee_minor         bigint NOT NULL DEFAULT 0 CHECK (fee_minor >= 0),
  delivery_days     int NOT NULL CHECK (delivery_days BETWEEN 1 AND 730),

  -- The four substantive fields. Lengths are floors, not decoration.
  cover_letter      text NOT NULL CHECK (length(btrim(cover_letter)) >= 120),
  approach          text NOT NULL CHECK (length(btrim(approach)) >= 120),
  relevant_experience text NOT NULL CHECK (length(btrim(relevant_experience)) >= 60),
  questions         text,

  status            text NOT NULL DEFAULT 'submitted' CHECK (status IN
                      ('draft','submitted','viewed','shortlisted','accepted','declined','withdrawn','expired')),
  -- Client-side triage, separate from status so shortlisting does not overwrite
  -- "viewed" and a decline reason survives.
  client_note       text,
  decline_reason    text,

  -- Denormalised snapshot of the match at submission time, so a later weight
  -- change does not silently rewrite history shown to the client.
  match_score       int CHECK (match_score IS NULL OR match_score BETWEEN 0 AND 100),
  match_breakdown   jsonb,

  viewed_at         timestamptz,
  shortlisted_at    timestamptz,
  responded_at      timestamptz,
  withdrawn_at      timestamptz,
  is_demo           boolean NOT NULL DEFAULT false,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);
-- One live proposal per developer per project; a withdrawn one may be replaced.
CREATE UNIQUE INDEX proposals_live_key ON proposals (project_id, developer_id)
  WHERE status NOT IN ('withdrawn','expired');
CREATE INDEX proposals_project_idx ON proposals (project_id, created_at DESC);
CREATE INDEX proposals_dev_idx     ON proposals (developer_id, created_at DESC);
CREATE INDEX proposals_ranking_idx ON proposals (project_id, match_score DESC NULLS LAST);
SELECT attach_touch_trigger('proposals');

-- Optional milestone plan proposed by the developer. Copied into the contract
-- on acceptance rather than referenced, so editing a proposal later cannot
-- rewrite a live contract.
CREATE TABLE proposal_milestones (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  proposal_id  uuid NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
  position     int NOT NULL CHECK (position >= 1),
  title        text NOT NULL,
  detail       text,
  amount_minor bigint NOT NULL CHECK (amount_minor > 0),
  days         int CHECK (days IS NULL OR days BETWEEN 1 AND 365),
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX proposal_milestones_position_key ON proposal_milestones (proposal_id, position);

-- Portfolio work the developer attaches as evidence. Either an AVERIX-verified
-- contract or an external portfolio item — exactly one of the two.
CREATE TABLE proposal_portfolio_links (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  proposal_id   uuid NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
  portfolio_project_id uuid,
  completed_history_id uuid,
  note          text,
  sort_order    int NOT NULL DEFAULT 100,
  created_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT proposal_portfolio_exactly_one CHECK (
    (portfolio_project_id IS NOT NULL)::int + (completed_history_id IS NOT NULL)::int = 1)
);
CREATE INDEX proposal_portfolio_links_proposal_idx ON proposal_portfolio_links (proposal_id, sort_order);

-- The matching engine's output, cached per (project, developer). Recomputed on
-- a weight change or a profile change; the explanation is stored alongside the
-- score because a score with no reasons is not shown anywhere in this product.
CREATE TABLE match_scores (
  project_id    uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  developer_id  uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  score         int NOT NULL CHECK (score BETWEEN 0 AND 100),
  -- {"technical": {"weight":0.35,"earned":0.31,"reasons":[{"label":"Python","met":true}]}, ...}
  breakdown     jsonb NOT NULL,
  -- The weight-set version this score was produced under.
  weights_version int NOT NULL,
  computed_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, developer_id)
);
CREATE INDEX match_scores_project_idx ON match_scores (project_id, score DESC);
CREATE INDEX match_scores_dev_idx     ON match_scores (developer_id, score DESC);

-- Admin-editable weights. Versioned so a change is auditable and cached scores
-- can be invalidated by comparing versions rather than truncating the cache.
CREATE TABLE matching_weights (
  version       int PRIMARY KEY,
  technical     numeric(4,3) NOT NULL DEFAULT 0.350,
  track_record  numeric(4,3) NOT NULL DEFAULT 0.200,
  github        numeric(4,3) NOT NULL DEFAULT 0.150,
  availability  numeric(4,3) NOT NULL DEFAULT 0.100,
  platform_history numeric(4,3) NOT NULL DEFAULT 0.100,
  budget_fit    numeric(4,3) NOT NULL DEFAULT 0.100,
  -- Below this score a project is not surfaced to a developer at all.
  feed_threshold int NOT NULL DEFAULT 35 CHECK (feed_threshold BETWEEN 0 AND 100),
  is_active     boolean NOT NULL DEFAULT false,
  note          text,
  created_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT matching_weights_sum CHECK (
    abs((technical + track_record + github + availability + platform_history + budget_fit) - 1.0) < 0.001)
);
CREATE UNIQUE INDEX matching_weights_active_key ON matching_weights ((true)) WHERE is_active;

INSERT INTO matching_weights (version, is_active, note)
VALUES (1, true, 'Launch defaults from the product specification.');
