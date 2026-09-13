-- 0023 простая регистрация: сначала аккаунт, потом выбор роли.
--
-- Раньше человек выбирал роль в той же форме, где вводил почту и пароль, —
-- до того, как увидел площадку. Теперь сначала создаётся аккаунт, а роль
-- выбирается следующим шагом, двумя большими карточками. Между этими двумя
-- моментами аккаунт существует и не имеет ни одной роли: у него нет ни строки
-- в user_roles, ни профиля. Это состояние и называется 'pending'.
--
-- Оно короткое, но настоящее: человек может закрыть вкладку между шагами и
-- вернуться завтра. Поэтому оно живёт в схеме, а не в памяти браузера.
ALTER TABLE sessions DROP CONSTRAINT sessions_active_role_check;
ALTER TABLE sessions ADD CONSTRAINT sessions_active_role_check
  CHECK (active_role IN ('pending','client','developer','admin','moderator'));

-- Вход через Google. Привязка по устойчивому идентификатору, а не по адресу:
-- адрес в Google можно сменить, и тогда вход по почте нашёл бы «другого»
-- человека — или, хуже, чужой аккаунт с таким же адресом.
ALTER TABLE users ADD COLUMN google_sub text;
CREATE UNIQUE INDEX users_google_sub_key ON users (google_sub)
  WHERE google_sub IS NOT NULL AND deleted_at IS NULL;

ALTER TABLE oauth_states DROP CONSTRAINT oauth_states_provider_check;
ALTER TABLE oauth_states ADD CONSTRAINT oauth_states_provider_check
  CHECK (provider IN ('github','google'));
