-- 0006 projects: client briefs, requirements, targeting inputs.

CREATE TABLE projects (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  -- Short human-readable reference printed in the UI and used in support threads.
  reference       text NOT NULL UNIQUE,
  client_id       uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  title           text NOT NULL CHECK (length(btrim(title)) BETWEEN 8 AND 140),
  slug            text NOT NULL,
  summary         text CHECK (summary IS NULL OR length(summary) <= 300),
  description     text NOT NULL CHECK (length(btrim(description)) >= 40),
  category_id     uuid NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,

  -- 'draft' while the client is still editing or reviewing the AI draft.
  status          text NOT NULL DEFAULT 'draft' CHECK (status IN
                    ('draft','pending_review','open','in_progress','completed','cancelled','expired')),
  visibility      text NOT NULL DEFAULT 'public'
                    CHECK (visibility IN ('public','invite_only','private')),

  -- Budget. A range is the norm; fixed sets both bounds equal.
  budget_type     text NOT NULL DEFAULT 'fixed' CHECK (budget_type IN ('fixed','range','hourly')),
  budget_min_minor bigint CHECK (budget_min_minor IS NULL OR budget_min_minor >= 0),
  budget_max_minor bigint CHECK (budget_max_minor IS NULL OR budget_max_minor >= 0),
  currency        char(3) NOT NULL DEFAULT 'USD',

  -- Timeline
  duration_days   int CHECK (duration_days IS NULL OR duration_days BETWEEN 1 AND 1095),
  deadline        date,
  starts          text CHECK (starts IS NULL OR starts IN ('immediately','within_week','within_month','flexible')),

  experience_wanted text CHECK (experience_wanted IS NULL OR experience_wanted IN
                      ('any','junior','mid','senior','lead')),
  -- Timezone overlap the client needs, as UTC offsets.
  overlap_from_utc int CHECK (overlap_from_utc IS NULL OR overlap_from_utc BETWEEN -12 AND 14),
  overlap_to_utc   int CHECK (overlap_to_utc IS NULL OR overlap_to_utc BETWEEN -12 AND 14),

  -- AI drafting provenance. The client always reviews before publishing, and the
  -- published text is theirs, so this records only how the draft began.
  origin          text NOT NULL DEFAULT 'manual'
                    CHECK (origin IN ('manual','assistant','template')),
  assistant_session_id uuid,

  proposals_count     int NOT NULL DEFAULT 0,
  invitations_count   int NOT NULL DEFAULT 0,
  views_count         int NOT NULL DEFAULT 0,
  shortlisted_count   int NOT NULL DEFAULT 0,
  hired_developer_id  uuid REFERENCES users(id) ON DELETE SET NULL,

  moderation_state text NOT NULL DEFAULT 'approved'
                     CHECK (moderation_state IN ('approved','pending','rejected','hidden')),
  moderation_note  text,

  -- Full-text document, maintained by the trigger below.
  search_doc      tsvector,

  published_at    timestamptz,
  expires_at      timestamptz,
  completed_at    timestamptz,
  cancelled_at    timestamptz,
  is_demo         boolean NOT NULL DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT projects_budget_order CHECK (
    budget_min_minor IS NULL OR budget_max_minor IS NULL OR budget_min_minor <= budget_max_minor),
  CONSTRAINT projects_published_has_time CHECK (status <> 'open' OR published_at IS NOT NULL)
);
CREATE UNIQUE INDEX projects_slug_key ON projects (slug);
CREATE INDEX projects_client_idx   ON projects (client_id, created_at DESC);
CREATE INDEX projects_open_idx     ON projects (published_at DESC)
  WHERE status = 'open' AND visibility = 'public' AND moderation_state = 'approved';
CREATE INDEX projects_category_idx ON projects (category_id, published_at DESC) WHERE status = 'open';
CREATE INDEX projects_search_idx   ON projects USING gin (search_doc);
CREATE INDEX projects_title_trgm   ON projects USING gin (title gin_trgm_ops);
CREATE INDEX projects_demo_idx     ON projects (is_demo) WHERE is_demo;
SELECT attach_touch_trigger('projects');

CREATE OR REPLACE FUNCTION projects_refresh_search_doc() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.search_doc :=
      setweight(to_tsvector('simple', coalesce(NEW.title, '')), 'A')
   || setweight(to_tsvector('simple', coalesce(NEW.summary, '')), 'B')
   || setweight(to_tsvector('english', coalesce(NEW.description, '')), 'C');
  RETURN NEW;
END;
$$;
CREATE TRIGGER projects_search_doc
  BEFORE INSERT OR UPDATE OF title, summary, description ON projects
  FOR EACH ROW EXECUTE FUNCTION projects_refresh_search_doc();

-- Required vs nice-to-have technologies. `is_required` is what the matcher
-- treats as a hard technical requirement.
CREATE TABLE project_skills (
  project_id  uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  skill_id    uuid NOT NULL REFERENCES skills(id) ON DELETE RESTRICT,
  is_required boolean NOT NULL DEFAULT true,
  PRIMARY KEY (project_id, skill_id)
);
CREATE INDEX project_skills_skill_idx ON project_skills (skill_id);

-- Specialisations the project is aimed at. Written by the targeting resolver
-- from the category, then adjustable by the client.
CREATE TABLE project_specialisations (
  project_id        uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  specialisation_id uuid NOT NULL REFERENCES specialisations(id) ON DELETE RESTRICT,
  relevance         numeric(3,2) NOT NULL DEFAULT 1.0 CHECK (relevance BETWEEN 0 AND 1),
  PRIMARY KEY (project_id, specialisation_id)
);
CREATE INDEX project_specialisations_spec_idx ON project_specialisations (specialisation_id);

-- The feature list a client approves in the wizard. These become the starting
-- point for milestones, so they are rows rather than prose.
CREATE TABLE project_features (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  title       text NOT NULL,
  detail      text,
  is_required boolean NOT NULL DEFAULT true,
  origin      text NOT NULL DEFAULT 'client' CHECK (origin IN ('client','assistant')),
  sort_order  int NOT NULL DEFAULT 100,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX project_features_project_idx ON project_features (project_id, sort_order);

-- Reference material the client attaches to the brief.
CREATE TABLE project_attachments (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  file_id     uuid NOT NULL,
  caption     text,
  sort_order  int NOT NULL DEFAULT 100,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX project_attachments_project_idx ON project_attachments (project_id, sort_order);

-- Direct invitations. A private project reaches developers only this way.
CREATE TABLE project_invitations (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id    uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  developer_id  uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  invited_by    uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  message       text,
  status        text NOT NULL DEFAULT 'sent'
                  CHECK (status IN ('sent','viewed','accepted','declined','expired')),
  responded_at  timestamptz,
  expires_at    timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX project_invitations_key ON project_invitations (project_id, developer_id);
CREATE INDEX project_invitations_dev_idx ON project_invitations (developer_id, created_at DESC);
SELECT attach_touch_trigger('project_invitations');

-- The transcript of the client-facing AI wizard. Kept so a client can resume a
-- half-finished brief, and so an admin can audit what the assistant proposed.
CREATE TABLE assistant_sessions (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id   uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  project_id  uuid REFERENCES projects(id) ON DELETE SET NULL,
  status      text NOT NULL DEFAULT 'active'
                CHECK (status IN ('active','drafted','published','abandoned')),
  -- [{"role":"assistant","content":"...","asked":"cart"}]
  transcript  jsonb NOT NULL DEFAULT '[]'::jsonb,
  -- The structured answers the questions produced.
  answers     jsonb NOT NULL DEFAULT '{}'::jsonb,
  -- The draft the client reviews. Never published without an explicit action.
  draft       jsonb,
  model       text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX assistant_sessions_client_idx ON assistant_sessions (client_id, updated_at DESC);
SELECT attach_touch_trigger('assistant_sessions');

ALTER TABLE projects ADD CONSTRAINT projects_assistant_session_fk
  FOREIGN KEY (assistant_session_id) REFERENCES assistant_sessions(id) ON DELETE SET NULL;
