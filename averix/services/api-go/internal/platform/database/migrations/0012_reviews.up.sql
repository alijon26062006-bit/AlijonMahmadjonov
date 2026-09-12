-- 0012 reviews.
--
-- A review requires a contract that reached 'completed'. The unique key on
-- (contract_id, author_id) means one review per side, and the foreign key means
-- a review with no contract behind it cannot exist.

CREATE TABLE reviews (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id   uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  author_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  subject_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  -- 'of_developer' uses the quality/communication/technical/deadline categories;
  -- 'of_client' uses communication/clarity/collaboration/payment.
  direction     text NOT NULL CHECK (direction IN ('of_developer','of_client')),

  overall       numeric(3,2) NOT NULL CHECK (overall BETWEEN 1 AND 5),
  -- Developer-facing categories
  quality       numeric(3,2) CHECK (quality IS NULL OR quality BETWEEN 1 AND 5),
  communication numeric(3,2) CHECK (communication IS NULL OR communication BETWEEN 1 AND 5),
  technical     numeric(3,2) CHECK (technical IS NULL OR technical BETWEEN 1 AND 5),
  deadline      numeric(3,2) CHECK (deadline IS NULL OR deadline BETWEEN 1 AND 5),
  -- Client-facing categories
  clarity       numeric(3,2) CHECK (clarity IS NULL OR clarity BETWEEN 1 AND 5),
  collaboration numeric(3,2) CHECK (collaboration IS NULL OR collaboration BETWEEN 1 AND 5),
  payment_reliability numeric(3,2) CHECK (payment_reliability IS NULL OR payment_reliability BETWEEN 1 AND 5),

  comment       text CHECK (comment IS NULL OR length(comment) <= 2000),
  would_work_again boolean,
  -- Both sides stay hidden until both have submitted or the window closes,
  -- so a review cannot be written in retaliation for one already seen.
  published_at  timestamptz,
  response      text CHECK (response IS NULL OR length(response) <= 1000),
  response_at   timestamptz,
  moderation_state text NOT NULL DEFAULT 'approved'
                     CHECK (moderation_state IN ('approved','pending','rejected','hidden')),
  is_demo       boolean NOT NULL DEFAULT false,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT reviews_parties_differ CHECK (author_id <> subject_id)
);
CREATE UNIQUE INDEX reviews_one_per_side_key ON reviews (contract_id, author_id);
CREATE INDEX reviews_subject_idx ON reviews (subject_id, created_at DESC)
  WHERE published_at IS NOT NULL AND moderation_state = 'approved';
SELECT attach_touch_trigger('reviews');

ALTER TABLE completed_project_history ADD CONSTRAINT completed_history_review_fk
  FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE SET NULL;

-- Recomputes the subject's rating aggregates from published, approved reviews.
CREATE OR REPLACE FUNCTION reviews_refresh_aggregates() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  sid uuid := coalesce(NEW.subject_id, OLD.subject_id);
  dir text := coalesce(NEW.direction, OLD.direction);
BEGIN
  IF dir = 'of_developer' THEN
    UPDATE developer_profiles p SET
      rating_avg           = agg.avg_overall,
      rating_count         = agg.n,
      rating_quality       = agg.avg_quality,
      rating_communication = agg.avg_comm,
      rating_technical     = agg.avg_tech,
      rating_deadline      = agg.avg_deadline,
      updated_at           = now()
    FROM (
      SELECT round(avg(overall), 2)       AS avg_overall,
             count(*)                     AS n,
             round(avg(quality), 2)       AS avg_quality,
             round(avg(communication), 2) AS avg_comm,
             round(avg(technical), 2)     AS avg_tech,
             round(avg(deadline), 2)      AS avg_deadline
        FROM reviews
       WHERE subject_id = sid AND direction = 'of_developer'
         AND published_at IS NOT NULL AND moderation_state = 'approved'
    ) agg
    WHERE p.user_id = sid;
  ELSE
    UPDATE client_profiles c SET
      rating_avg = agg.avg_overall, rating_count = agg.n, updated_at = now()
    FROM (
      SELECT round(avg(overall), 2) AS avg_overall, count(*) AS n
        FROM reviews
       WHERE subject_id = sid AND direction = 'of_client'
         AND published_at IS NOT NULL AND moderation_state = 'approved'
    ) agg
    WHERE c.user_id = sid;
  END IF;
  RETURN NULL;
END;
$$;
CREATE TRIGGER reviews_refresh
  AFTER INSERT OR UPDATE OF overall, quality, communication, technical, deadline,
    published_at, moderation_state OR DELETE ON reviews
  FOR EACH ROW EXECUTE FUNCTION reviews_refresh_aggregates();
