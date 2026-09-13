DELETE FROM platform_settings WHERE key IN (
  'platform.fee_basis_points','contracts.auto_approve_days','contracts.confirm_hours',
  'services.max_new','services.max_advanced','services.max_professional');

DELETE FROM notifications WHERE type IN (
  'milestone_auto_approved','order_awaiting_confirmation','order_confirmed',
  'order_declined','order_expired','seller_level_changed');
ALTER TABLE notifications DROP CONSTRAINT notifications_type_check;
ALTER TABLE notifications ADD CONSTRAINT notifications_type_check
  CHECK (type IN (
    'proposal_received','proposal_accepted','proposal_declined','proposal_shortlisted',
    'project_invitation','project_published','project_recommended',
    'message_received',
    'milestone_submitted','milestone_revision_requested','milestone_approved','milestone_released',
    'payment_succeeded','payment_failed','payment_refunded',
    'review_received','review_published',
    'github_analysis_complete','github_analysis_failed',
    'contract_started','contract_completed','contract_cancelled',
    'dispute_opened','dispute_resolved',
    'account_verified','account_warning','account_suspended',
    'identity_submitted','identity_approved','identity_rejected','identity_resubmit_requested',
    'profile_submitted','profile_approved'));

DROP INDEX IF EXISTS developer_profiles_level_idx;
ALTER TABLE developer_profiles
  DROP COLUMN seller_level_updated_at,
  DROP COLUMN seller_level;

DROP INDEX IF EXISTS milestones_auto_approve_idx;
ALTER TABLE milestones DROP COLUMN auto_approve_at;

DROP INDEX IF EXISTS contracts_awaiting_confirmation_idx;
ALTER TABLE contracts
  DROP COLUMN developer_confirmed_at,
  DROP COLUMN developer_confirm_deadline;

DROP TABLE contract_options;
DROP TABLE service_options;
