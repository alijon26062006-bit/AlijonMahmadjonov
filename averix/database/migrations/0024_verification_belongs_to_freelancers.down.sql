DELETE FROM platform_settings WHERE key = 'identity.required_for_work';

DROP TRIGGER IF EXISTS identity_verifications_freelancer_only ON identity_verifications;
DROP FUNCTION IF EXISTS identity_requires_freelancer();
