ALTER TABLE IF EXISTS completed_project_history DROP CONSTRAINT IF EXISTS completed_history_review_fk;
DROP TABLE IF EXISTS reviews;
DROP FUNCTION IF EXISTS reviews_refresh_aggregates();
