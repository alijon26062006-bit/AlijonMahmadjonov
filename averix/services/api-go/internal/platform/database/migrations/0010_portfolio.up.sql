-- 0010 portfolio and the AVERIX-verified project history.
--
-- Two distinct things that the UI must never blur:
--   portfolio_projects        — self-declared work. Trust: the developer's word.
--   completed_project_history — generated from a finished AVERIX contract.
--                               Trust: the platform's. Cannot be inserted by a user.

CREATE TABLE portfolio_projects (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  developer_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  slug            text NOT NULL,
  title           text NOT NULL CHECK (length(btrim(title)) BETWEEN 3 AND 120),
  short_description text CHECK (short_description IS NULL OR length(short_description) <= 200),
  description     text,
  category_id     uuid REFERENCES categories(id) ON DELETE SET NULL,
  developer_role  text CHECK (developer_role IS NULL OR length(developer_role) <= 120),

  cover_file_id   uuid REFERENCES files(id) ON DELETE SET NULL,

  -- Normalised, validated, HTTPS-only. See the URL security rules in the API.
  project_url     text,
  project_url_host text,
  -- Result of the embeddability probe: can this be shown in the in-app browser?
  embeddable      text NOT NULL DEFAULT 'unknown'
                    CHECK (embeddable IN ('unknown','allowed','blocked','unreachable')),
  embeddable_reason text,
  embeddable_checked_at timestamptz,
  repository_url  text,

  completed_on    date,
  duration_days   int CHECK (duration_days IS NULL OR duration_days > 0),
  -- Optional and the developer's choice, with the same visibility ladder the
  -- verified history uses.
  value_minor     bigint CHECK (value_minor IS NULL OR value_minor >= 0),
  currency        char(3) NOT NULL DEFAULT 'USD',
  value_visibility text NOT NULL DEFAULT 'hidden' CHECK (value_visibility IN
                     ('public','range','hidden','private')),

  demo_status     text NOT NULL DEFAULT 'none' CHECK (demo_status IN
                    ('none','live','staging','offline','private_repo','nda')),
  is_published    boolean NOT NULL DEFAULT false,
  is_featured     boolean NOT NULL DEFAULT false,
  sort_order      int NOT NULL DEFAULT 100,
  view_count      int NOT NULL DEFAULT 0,
  moderation_state text NOT NULL DEFAULT 'approved'
                     CHECK (moderation_state IN ('approved','pending','rejected','hidden')),
  moderation_note text,
  search_doc      tsvector,
  is_demo         boolean NOT NULL DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX portfolio_projects_slug_key ON portfolio_projects (developer_id, slug);
CREATE INDEX portfolio_projects_dev_idx ON portfolio_projects (developer_id, sort_order)
  WHERE is_published AND moderation_state = 'approved';
CREATE INDEX portfolio_projects_search_idx ON portfolio_projects USING gin (search_doc);
SELECT attach_touch_trigger('portfolio_projects');

CREATE OR REPLACE FUNCTION portfolio_refresh_search_doc() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.search_doc :=
      setweight(to_tsvector('simple',  coalesce(NEW.title, '')), 'A')
   || setweight(to_tsvector('simple',  coalesce(NEW.short_description, '')), 'B')
   || setweight(to_tsvector('english', coalesce(NEW.description, '')), 'C');
  RETURN NEW;
END;
$$;
CREATE TRIGGER portfolio_search_doc
  BEFORE INSERT OR UPDATE OF title, short_description, description ON portfolio_projects
  FOR EACH ROW EXECUTE FUNCTION portfolio_refresh_search_doc();

-- Ordered gallery. The row at position 0 is the cover unless cover_file_id
-- overrides it.
CREATE TABLE portfolio_images (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  portfolio_project_id uuid NOT NULL REFERENCES portfolio_projects(id) ON DELETE CASCADE,
  file_id      uuid NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  caption      text CHECK (caption IS NULL OR length(caption) <= 160),
  alt_text     text CHECK (alt_text IS NULL OR length(alt_text) <= 200),
  position     int NOT NULL DEFAULT 0,
  placeholder  text,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX portfolio_images_position_key ON portfolio_images (portfolio_project_id, position);
CREATE INDEX portfolio_images_project_idx ON portfolio_images (portfolio_project_id, position);

CREATE TABLE portfolio_skills (
  portfolio_project_id uuid NOT NULL REFERENCES portfolio_projects(id) ON DELETE CASCADE,
  skill_id             uuid NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
  PRIMARY KEY (portfolio_project_id, skill_id)
);
CREATE INDEX portfolio_skills_skill_idx ON portfolio_skills (skill_id);

-- Extra links (case study, app store, article). Validated the same way as
-- project_url; nothing here is fetched by the backend.
CREATE TABLE portfolio_links (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  portfolio_project_id uuid NOT NULL REFERENCES portfolio_projects(id) ON DELETE CASCADE,
  label        text NOT NULL,
  url          text NOT NULL,
  url_host     text NOT NULL,
  kind         text NOT NULL DEFAULT 'other' CHECK (kind IN
                 ('live','repository','case_study','app_store','play_store','article','other')),
  sort_order   int NOT NULL DEFAULT 100,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX portfolio_links_project_idx ON portfolio_links (portfolio_project_id, sort_order);

-- Verified history. Written only by the contract-completion path; the API
-- exposes no insert or update, and the unique key on contract_id makes a
-- duplicate impossible even if that path ran twice.
CREATE TABLE completed_project_history (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  developer_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  contract_id     uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  project_id      uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  client_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,

  title           text NOT NULL,
  summary         text,
  category_id     uuid REFERENCES categories(id) ON DELETE SET NULL,

  client_rating   numeric(3,2) CHECK (client_rating IS NULL OR client_rating BETWEEN 1 AND 5),
  review_id       uuid,

  value_minor     bigint NOT NULL,
  currency        char(3) NOT NULL DEFAULT 'USD',
  -- Copied from the contract at completion so a later contract edit cannot
  -- retroactively expose a figure the parties agreed to keep private.
  value_visibility text NOT NULL CHECK (value_visibility IN ('public','range','hidden','private')),

  duration_days   int,
  completed_at    timestamptz NOT NULL,
  -- The developer may hide an entry from their profile but never fabricate one.
  is_visible      boolean NOT NULL DEFAULT true,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX completed_history_contract_key ON completed_project_history (contract_id);
CREATE INDEX completed_history_dev_idx ON completed_project_history (developer_id, completed_at DESC)
  WHERE is_visible;

CREATE TABLE completed_project_skills (
  history_id uuid NOT NULL REFERENCES completed_project_history(id) ON DELETE CASCADE,
  skill_id   uuid NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
  PRIMARY KEY (history_id, skill_id)
);

ALTER TABLE proposal_portfolio_links ADD CONSTRAINT proposal_portfolio_project_fk
  FOREIGN KEY (portfolio_project_id) REFERENCES portfolio_projects(id) ON DELETE CASCADE;
ALTER TABLE proposal_portfolio_links ADD CONSTRAINT proposal_portfolio_history_fk
  FOREIGN KEY (completed_history_id) REFERENCES completed_project_history(id) ON DELETE CASCADE;
