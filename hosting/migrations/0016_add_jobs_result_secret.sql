-- Короткоживущее место для передачи одноразового секрета (например, пароля новой БД)
-- от воркера панели. Панель читает это поле один раз сразу после успеха задания
-- и тут же затирает его (UPDATE ... SET result_secret = NULL) — см. JobRepository::consumeResultSecret.
ALTER TABLE jobs ADD COLUMN result_secret TEXT NULL AFTER error_text;
