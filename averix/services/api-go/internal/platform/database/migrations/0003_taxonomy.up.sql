-- 0003 taxonomy: specialisations, categories, technologies.
--
-- AVERIX is a software-only marketplace, so the taxonomy is deliberately closed.
-- Three levels that each answer a different question:
--   specialisations — "what kind of engineer are you?"   (one primary per developer)
--   categories      — "what kind of work is this?"       (hierarchical, on projects)
--   skills          — "what is it built with?"           (technologies, on both)
-- Targeting joins on all three, which is why they are separate tables rather
-- than one bag of tags.

CREATE TABLE specialisations (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug        text NOT NULL UNIQUE,
  name        text NOT NULL,
  short_name  text NOT NULL,
  description text,
  icon        text,
  sort_order  int NOT NULL DEFAULT 100,
  is_active   boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
SELECT attach_touch_trigger('specialisations');

CREATE TABLE categories (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  parent_id   uuid REFERENCES categories(id) ON DELETE RESTRICT,
  slug        text NOT NULL UNIQUE,
  name        text NOT NULL,
  description text,
  icon        text,
  -- Materialised ancestry so a subtree query is one index scan, not a recursion.
  path        text NOT NULL,
  depth       int NOT NULL DEFAULT 0 CHECK (depth BETWEEN 0 AND 3),
  sort_order  int NOT NULL DEFAULT 100,
  is_active   boolean NOT NULL DEFAULT true,
  project_count int NOT NULL DEFAULT 0,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX categories_parent_idx ON categories (parent_id, sort_order);
CREATE INDEX categories_path_idx   ON categories (path text_pattern_ops);
SELECT attach_touch_trigger('categories');

CREATE TABLE skills (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug         text NOT NULL UNIQUE,
  name         text NOT NULL,
  -- 'language' | 'framework' | 'database' | 'platform' | 'tool' | 'cloud' | 'protocol' | 'practice'
  kind         text NOT NULL CHECK (kind IN
                 ('language','framework','database','platform','tool','cloud','protocol','practice')),
  -- The language/platform this belongs to, e.g. FastAPI -> Python. Drives the
  -- "Python: FastAPI, Django, Flask" grouping in the project wizard.
  parent_id    uuid REFERENCES skills(id) ON DELETE SET NULL,
  -- Names GitHub reports for this technology, used by the analysis service.
  github_aliases text[] NOT NULL DEFAULT '{}',
  -- Manifest files that prove the technology is in use.
  manifest_hints text[] NOT NULL DEFAULT '{}',
  colour       text,
  is_active    boolean NOT NULL DEFAULT true,
  usage_count  int NOT NULL DEFAULT 0,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX skills_kind_idx   ON skills (kind) WHERE is_active;
CREATE INDEX skills_parent_idx ON skills (parent_id);
CREATE INDEX skills_name_trgm  ON skills USING gin (name gin_trgm_ops);
CREATE INDEX skills_aliases_idx ON skills USING gin (github_aliases);
SELECT attach_touch_trigger('skills');

-- Which technologies are plausible for a specialisation. Used to keep the
-- onboarding technology picker relevant instead of showing all 200 options.
CREATE TABLE specialisation_skills (
  specialisation_id uuid NOT NULL REFERENCES specialisations(id) ON DELETE CASCADE,
  skill_id          uuid NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
  is_core           boolean NOT NULL DEFAULT false,
  PRIMARY KEY (specialisation_id, skill_id)
);

CREATE TABLE category_skills (
  category_id uuid NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
  skill_id    uuid NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
  weight      numeric(3,2) NOT NULL DEFAULT 1.0 CHECK (weight BETWEEN 0 AND 1),
  PRIMARY KEY (category_id, skill_id)
);

-- A specialisation is relevant to a category with a strength. This is the table
-- the targeting engine reads to decide that a Telegram bot project belongs in a
-- Telegram or Python-backend developer's feed and not an iOS developer's.
CREATE TABLE category_specialisations (
  category_id       uuid NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
  specialisation_id uuid NOT NULL REFERENCES specialisations(id) ON DELETE CASCADE,
  relevance         numeric(3,2) NOT NULL DEFAULT 1.0 CHECK (relevance BETWEEN 0 AND 1),
  PRIMARY KEY (category_id, specialisation_id)
);
