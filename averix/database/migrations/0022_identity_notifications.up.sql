-- 0022 уведомления о проверке личности.
--
-- Человек должен узнать о решении, не заходя в админку и не получая при этом
-- ничего из самого документа: только то, что решение принято и где оно.
-- Тексты и ссылки формируются в коде; здесь только разрешённые типы.
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
    'identity_submitted','identity_approved','identity_rejected','identity_resubmit_requested'));
