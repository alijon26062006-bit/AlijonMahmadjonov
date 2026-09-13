-- 0025 анкета исполнителя — это заявка.
--
-- Раньше последний шаг анкеты сразу публиковал её в каталоге. Теперь он
-- отправляет заявку человеку: администратор смотрит профиль и работы и решает.
-- До решения исполнитель видит «Заявка на рассмотрении», а в каталоге его нет.
--
-- Решение нужно как-то сообщить, а типы уведомлений в этой схеме — закрытый
-- список, поэтому он расширяется здесь.
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
