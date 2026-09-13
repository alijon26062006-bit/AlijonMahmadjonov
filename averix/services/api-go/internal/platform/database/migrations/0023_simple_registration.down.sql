ALTER TABLE oauth_states DROP CONSTRAINT oauth_states_provider_check;
DELETE FROM oauth_states WHERE provider = 'google';
ALTER TABLE oauth_states ADD CONSTRAINT oauth_states_provider_check
  CHECK (provider IN ('github'));

DROP INDEX IF EXISTS users_google_sub_key;
ALTER TABLE users DROP COLUMN IF EXISTS google_sub;

-- Сессии, где роль ещё не выбрана, отзываются: без роли они не работают в
-- старой схеме, а человек просто войдёт заново.
DELETE FROM sessions WHERE active_role = 'pending';
ALTER TABLE sessions DROP CONSTRAINT sessions_active_role_check;
ALTER TABLE sessions ADD CONSTRAINT sessions_active_role_check
  CHECK (active_role IN ('client','developer','admin','moderator'));
