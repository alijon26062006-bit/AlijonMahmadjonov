-- 0004 profiles: client and developer profiles, photos, skills, availability.

CREATE TABLE client_profiles (
  user_id            uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  company_name       text,
  company_website    text,
  company_size       text CHECK (company_size IS NULL OR company_size IN
                       ('solo','2-10','11-50','51-200','200+')),
  industry           text,
  about              text CHECK (about IS NULL OR length(about) <= 2000),
  -- Denormalised counters, maintained by the contract lifecycle. Reading a
  -- profile must not aggregate the whole contract table.
  projects_posted    int NOT NULL DEFAULT 0,
  hires_made         int NOT NULL DEFAULT 0,
  total_spent_minor  bigint NOT NULL DEFAULT 0,
  spend_currency     char(3) NOT NULL DEFAULT 'USD',
  rating_avg         numeric(3,2),
  rating_count       int NOT NULL DEFAULT 0,
  payment_verified_at timestamptz,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);
SELECT attach_touch_trigger('client_profiles');

CREATE TABLE developer_profiles (
  user_id                uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  -- Exactly one primary specialisation, enforced by living on this row rather
  -- than in the join table. The public profile's title comes from here.
  primary_specialisation_id uuid REFERENCES specialisations(id) ON DELETE RESTRICT,
  professional_title     text CHECK (professional_title IS NULL OR length(professional_title) <= 80),
  bio                    text CHECK (bio IS NULL OR length(bio) <= 3000),
  experience_level       text CHECK (experience_level IS NULL OR experience_level IN
                           ('junior','mid','senior','lead')),
  years_experience       int CHECK (years_experience IS NULL OR years_experience BETWEEN 0 AND 50),
  hourly_rate_minor      bigint CHECK (hourly_rate_minor IS NULL OR hourly_rate_minor >= 0),
  rate_currency          char(3) NOT NULL DEFAULT 'USD',
  min_project_minor      bigint CHECK (min_project_minor IS NULL OR min_project_minor >= 0),

  -- Availability
  availability           text NOT NULL DEFAULT 'unavailable'
                           CHECK (availability IN ('available','limited','booked','unavailable')),
  hours_per_week         int CHECK (hours_per_week IS NULL OR hours_per_week BETWEEN 1 AND 80),
  available_from         date,
  -- Timezone overlap the developer will commit to, as UTC offsets.
  overlap_from_utc       int CHECK (overlap_from_utc IS NULL OR overlap_from_utc BETWEEN -12 AND 14),
  overlap_to_utc         int CHECK (overlap_to_utc IS NULL OR overlap_to_utc BETWEEN -12 AND 14),

  -- Public surface controls
  show_location          boolean NOT NULL DEFAULT true,
  show_hourly_rate       boolean NOT NULL DEFAULT true,
  open_to_invitations    boolean NOT NULL DEFAULT true,

  -- Reputation, all derived from completed AVERIX contracts.
  rating_avg             numeric(3,2),
  rating_count           int NOT NULL DEFAULT 0,
  rating_quality         numeric(3,2),
  rating_communication   numeric(3,2),
  rating_technical       numeric(3,2),
  rating_deadline        numeric(3,2),
  projects_completed     int NOT NULL DEFAULT 0,
  projects_cancelled     int NOT NULL DEFAULT 0,
  success_rate           numeric(5,2),
  on_time_rate           numeric(5,2),
  repeat_client_count    int NOT NULL DEFAULT 0,
  -- Rolling median first-response time to a client message, in seconds.
  response_time_seconds  int,
  total_earned_minor     bigint NOT NULL DEFAULT 0,   -- private; never serialised publicly
  earnings_currency      char(3) NOT NULL DEFAULT 'USD',

  -- Onboarding
  onboarding_step        int NOT NULL DEFAULT 1 CHECK (onboarding_step BETWEEN 1 AND 10),
  onboarding_completed_at timestamptz,
  profile_completeness   int NOT NULL DEFAULT 0 CHECK (profile_completeness BETWEEN 0 AND 100),

  -- Moderation / discovery
  is_searchable          boolean NOT NULL DEFAULT false,
  is_featured            boolean NOT NULL DEFAULT false,
  moderation_state       text NOT NULL DEFAULT 'approved'
                           CHECK (moderation_state IN ('approved','pending','rejected','hidden')),
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT developer_overlap_order CHECK (
    overlap_from_utc IS NULL OR overlap_to_utc IS NULL OR overlap_from_utc <= overlap_to_utc)
);
CREATE INDEX developer_profiles_spec_idx ON developer_profiles (primary_specialisation_id)
  WHERE is_searchable;
CREATE INDEX developer_profiles_avail_idx ON developer_profiles (availability)
  WHERE is_searchable;
CREATE INDEX developer_profiles_rating_idx ON developer_profiles (rating_avg DESC NULLS LAST)
  WHERE is_searchable;
SELECT attach_touch_trigger('developer_profiles');

-- Up to three additional specialisations, capped by a trigger below.
CREATE TABLE developer_specialisations (
  user_id           uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  specialisation_id uuid NOT NULL REFERENCES specialisations(id) ON DELETE CASCADE,
  created_at        timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, specialisation_id)
);

CREATE OR REPLACE FUNCTION enforce_additional_specialisation_cap() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM developer_specialisations WHERE user_id = NEW.user_id;
  IF n > 3 THEN
    RAISE EXCEPTION 'a developer may hold at most 3 additional specialisations'
      USING ERRCODE = 'check_violation';
  END IF;
  -- An additional specialisation may not duplicate the primary one.
  IF EXISTS (SELECT 1 FROM developer_profiles p
             WHERE p.user_id = NEW.user_id
               AND p.primary_specialisation_id = NEW.specialisation_id) THEN
    RAISE EXCEPTION 'additional specialisation duplicates the primary specialisation'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$;
CREATE CONSTRAINT TRIGGER developer_specialisations_cap
  AFTER INSERT OR UPDATE ON developer_specialisations
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION enforce_additional_specialisation_cap();

CREATE TABLE developer_skills (
  user_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  skill_id      uuid NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
  -- Self-declared proficiency. Deliberately coarse: GitHub code share is never
  -- converted into a knowledge percentage anywhere in this product.
  level         text NOT NULL DEFAULT 'working'
                  CHECK (level IN ('familiar','working','strong','expert')),
  years         int CHECK (years IS NULL OR years BETWEEN 0 AND 50),
  is_primary    boolean NOT NULL DEFAULT false,
  -- Set when the skill is corroborated by GitHub analysis or a completed contract.
  evidence      text[] NOT NULL DEFAULT '{}',
  sort_order    int NOT NULL DEFAULT 100,
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, skill_id)
);
CREATE INDEX developer_skills_skill_idx ON developer_skills (skill_id);

CREATE OR REPLACE FUNCTION enforce_primary_skill_cap() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM developer_skills WHERE user_id = NEW.user_id AND is_primary;
  IF n > 15 THEN
    RAISE EXCEPTION 'a developer may list at most 15 primary technologies'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$;
CREATE CONSTRAINT TRIGGER developer_skills_primary_cap
  AFTER INSERT OR UPDATE ON developer_skills
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION enforce_primary_skill_cap();

-- Profile photos. The original is kept private; the derivatives are what the
-- product serves. Crop geometry is stored so the user can re-crop later without
-- re-uploading.
CREATE TABLE developer_photos (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  -- Object-storage keys. Random, never derived from the uploaded filename.
  original_key   text NOT NULL,
  original_bytes bigint NOT NULL,
  original_mime  text NOT NULL,
  original_width  int NOT NULL,
  original_height int NOT NULL,
  -- Normalised crop rectangle in source pixels + rotation, replayable losslessly.
  crop_x         int NOT NULL DEFAULT 0,
  crop_y         int NOT NULL DEFAULT 0,
  crop_w         int NOT NULL,
  crop_h         int NOT NULL,
  rotation       int NOT NULL DEFAULT 0 CHECK (rotation IN (0,90,180,270)),
  crop_shape     text NOT NULL DEFAULT 'circle' CHECK (crop_shape IN ('circle','rounded')),
  -- {"avif": {"256": "key", ...}, "webp": {...}, "jpeg": {...}}
  derivatives    jsonb NOT NULL DEFAULT '{}'::jsonb,
  -- Average colour of the crop, used as the blur-up placeholder.
  placeholder    text,
  is_current     boolean NOT NULL DEFAULT true,
  moderation_state text NOT NULL DEFAULT 'approved'
                     CHECK (moderation_state IN ('approved','pending','rejected')),
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT developer_photos_crop_positive CHECK (crop_w > 0 AND crop_h > 0)
);
CREATE UNIQUE INDEX developer_photos_current_key ON developer_photos (user_id) WHERE is_current;
SELECT attach_touch_trigger('developer_photos');

-- Spoken languages, shown on the public profile.
CREATE TABLE user_languages (
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  language    text NOT NULL,
  proficiency text NOT NULL DEFAULT 'conversational'
                CHECK (proficiency IN ('basic','conversational','fluent','native')),
  PRIMARY KEY (user_id, language)
);
