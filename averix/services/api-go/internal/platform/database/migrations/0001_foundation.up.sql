-- 0001 foundation: extensions, shared helpers, conventions.
--
-- Conventions used by every later migration:
--   * primary keys are uuid v4 — resource ids are never guessable, so a leaked
--     or enumerated id cannot be used to probe the API (authorisation is still
--     checked on every read; the uuid is defence in depth, not the defence)
--   * money is stored as integer minor units + ISO-4217 currency, never float
--   * every table carries created_at; mutable tables carry updated_at,
--     maintained by the touch_updated_at() trigger
--   * state machines are text + CHECK so a new state is one migration, not a
--     type rewrite with a table lock

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid(), crypt()
CREATE EXTENSION IF NOT EXISTS citext;     -- case-insensitive email / username
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- trigram search on names and titles
CREATE EXTENSION IF NOT EXISTS btree_gin;  -- composite gin indexes for the feed

CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

-- Applies the updated_at trigger without repeating the boilerplate 30 times.
CREATE OR REPLACE FUNCTION attach_touch_trigger(tbl regclass) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
  EXECUTE format(
    'CREATE TRIGGER %I BEFORE UPDATE ON %s FOR EACH ROW EXECUTE FUNCTION touch_updated_at()',
    'touch_' || replace(tbl::text, '.', '_'), tbl);
END;
$$;

-- unaccent is a contrib module that may be unavailable on managed Postgres;
-- this fallback keeps slugify() working without it.
CREATE OR REPLACE FUNCTION unaccent_fallback(input text) RETURNS text
LANGUAGE sql IMMUTABLE STRICT AS $$
  SELECT translate(input,
    'àáâãäåèéêëìíîïòóôõöùúûüýÿñçšžÀÁÂÃÄÅÈÉÊËÌÍÎÏÒÓÔÕÖÙÚÛÜÝÑÇŠŽ',
    'aaaaaaeeeeiiiiooooouuuuyyncszAAAAAAEEEEIIIIOOOOOUUUUYNCSZ');
$$;

-- A slug that is safe in a URL and stable enough to print on a profile.
CREATE OR REPLACE FUNCTION slugify(input text) RETURNS text
LANGUAGE sql IMMUTABLE STRICT AS $$
  SELECT trim(both '-' from regexp_replace(lower(unaccent_fallback(input)), '[^a-z0-9]+', '-', 'g'));
$$;

CREATE TABLE schema_meta (
  key        text PRIMARY KEY,
  value      jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
SELECT attach_touch_trigger('schema_meta');

INSERT INTO schema_meta (key, value) VALUES
  ('platform', '{"name":"AVERIX","vertical":"software-development"}'::jsonb);
