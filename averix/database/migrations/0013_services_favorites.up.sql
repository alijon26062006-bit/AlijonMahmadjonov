-- 0013 fixed-price services, saved items.

CREATE TABLE services (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  developer_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  slug            text NOT NULL,
  title           text NOT NULL CHECK (length(btrim(title)) BETWEEN 8 AND 120),
  summary         text CHECK (summary IS NULL OR length(summary) <= 240),
  description     text NOT NULL CHECK (length(btrim(description)) >= 80),
  category_id     uuid NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
  cover_file_id   uuid REFERENCES files(id) ON DELETE SET NULL,

  -- "From $300": the floor for the base tier.
  from_minor      bigint NOT NULL CHECK (from_minor > 0),
  currency        char(3) NOT NULL DEFAULT 'USD',
  delivery_days   int NOT NULL CHECK (delivery_days BETWEEN 1 AND 365),
  revisions       int NOT NULL DEFAULT 1 CHECK (revisions BETWEEN 0 AND 10),

  status          text NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft','active','paused','archived')),
  orders_count    int NOT NULL DEFAULT 0,
  view_count      int NOT NULL DEFAULT 0,
  rating_avg      numeric(3,2),
  rating_count    int NOT NULL DEFAULT 0,
  moderation_state text NOT NULL DEFAULT 'approved'
                     CHECK (moderation_state IN ('approved','pending','rejected','hidden')),
  search_doc      tsvector,
  is_demo         boolean NOT NULL DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX services_slug_key ON services (developer_id, slug);
CREATE INDEX services_active_idx ON services (category_id, from_minor)
  WHERE status = 'active' AND moderation_state = 'approved';
CREATE INDEX services_dev_idx ON services (developer_id);
CREATE INDEX services_search_idx ON services USING gin (search_doc);
SELECT attach_touch_trigger('services');

CREATE OR REPLACE FUNCTION services_refresh_search_doc() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.search_doc :=
      setweight(to_tsvector('simple',  coalesce(NEW.title, '')), 'A')
   || setweight(to_tsvector('simple',  coalesce(NEW.summary, '')), 'B')
   || setweight(to_tsvector('english', coalesce(NEW.description, '')), 'C');
  RETURN NEW;
END;
$$;
CREATE TRIGGER services_search_doc
  BEFORE INSERT OR UPDATE OF title, summary, description ON services
  FOR EACH ROW EXECUTE FUNCTION services_refresh_search_doc();

CREATE TABLE service_skills (
  service_id uuid NOT NULL REFERENCES services(id) ON DELETE CASCADE,
  skill_id   uuid NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
  PRIMARY KEY (service_id, skill_id)
);

CREATE TABLE service_tiers (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  service_id   uuid NOT NULL REFERENCES services(id) ON DELETE CASCADE,
  position     int NOT NULL CHECK (position BETWEEN 1 AND 3),
  name         text NOT NULL,
  price_minor  bigint NOT NULL CHECK (price_minor > 0),
  delivery_days int NOT NULL CHECK (delivery_days BETWEEN 1 AND 365),
  revisions    int NOT NULL DEFAULT 1,
  includes     text[] NOT NULL DEFAULT '{}',
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX service_tiers_position_key ON service_tiers (service_id, position);

CREATE TABLE service_portfolio_links (
  service_id uuid NOT NULL REFERENCES services(id) ON DELETE CASCADE,
  portfolio_project_id uuid NOT NULL REFERENCES portfolio_projects(id) ON DELETE CASCADE,
  sort_order int NOT NULL DEFAULT 100,
  PRIMARY KEY (service_id, portfolio_project_id)
);

CREATE TABLE saved_developers (
  client_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  developer_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  note         text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (client_id, developer_id),
  CONSTRAINT saved_developers_not_self CHECK (client_id <> developer_id)
);
CREATE INDEX saved_developers_client_idx ON saved_developers (client_id, created_at DESC);

CREATE TABLE saved_projects (
  developer_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  project_id   uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  note         text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (developer_id, project_id)
);
CREATE INDEX saved_projects_dev_idx ON saved_projects (developer_id, created_at DESC);

-- Feed impressions. Powers "recent", dedupes the feed, and gives the matching
-- engine something to measure itself against.
CREATE TABLE project_views (
  id           bigserial PRIMARY KEY,
  project_id   uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  viewer_id    uuid REFERENCES users(id) ON DELETE SET NULL,
  source       text CHECK (source IS NULL OR source IN
                 ('feed','search','invitation','direct','saved','profile')),
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX project_views_project_idx ON project_views (project_id, created_at DESC);
CREATE INDEX project_views_viewer_idx  ON project_views (viewer_id, created_at DESC);
