DELETE FROM platform_settings WHERE key IN ('identity.retention_days', 'identity.selfie_with_document');

DROP INDEX IF EXISTS users_email_trgm;
DROP INDEX IF EXISTS users_full_name_trgm;

UPDATE users SET status = 'suspended' WHERE status = 'banned';
ALTER TABLE users DROP CONSTRAINT users_status_check;
ALTER TABLE users ADD CONSTRAINT users_status_check
  CHECK (status IN ('pending','active','suspended','deactivated'));

DROP INDEX IF EXISTS users_phone_digits;
ALTER TABLE users DROP COLUMN IF EXISTS phone_digits;
ALTER TABLE users DROP COLUMN IF EXISTS phone;

DROP TABLE IF EXISTS admin_access_logs;
DROP TABLE IF EXISTS identity_review_actions;
DROP TABLE IF EXISTS identity_documents;
DROP TABLE IF EXISTS identity_verifications;
DROP TABLE IF EXISTS admin_permission_grants;
