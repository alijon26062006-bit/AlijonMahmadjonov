-- 0026 четыре вещи, которых не хватало рядом с деньгами.
--
--   1. Опции к услуге. Пакет — это то, что входит в цену; опция — то, что
--      заказчик докупает к нему сам: «сделать за день», «отдать исходники»,
--      «ещё два варианта». Без них исполнитель либо раздувает пакет, либо
--      теряет деньги на каждом заказе, где нужно чуть больше.
--
--   2. Подтверждение заказа исполнителем. Услугу заказывают без переговоров,
--      и до сих пор сделка открывалась, даже если исполнитель в отпуске.
--      Теперь у него есть срок, чтобы принять заказ, а у заказчика —
--      уверенность, что молчание закончится возвратом, а не ожиданием.
--
--   3. Автоприёмка сданной работы. Этап в состоянии «сдан» мог висеть вечно,
--      если заказчик пропал: деньги исполнителя заморожены, и сделать он
--      ничего не мог. Теперь у сдачи есть срок, после которого работа
--      принимается сама.
--
--   4. Уровень исполнителя. Он считается из завершённых сделок, доли провалов
--      и рейтинга, пересчитывается фоном и теряется так же, как получается.
--      Это и сигнал доверия заказчику, и естественный лимит на число услуг.

-- ── 1. Опции к услуге ───────────────────────────────────────────────────────

CREATE TABLE service_options (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  service_id    uuid NOT NULL REFERENCES services(id) ON DELETE CASCADE,
  position      int NOT NULL CHECK (position BETWEEN 1 AND 10),
  name          text NOT NULL CHECK (length(btrim(name)) BETWEEN 3 AND 80),
  price_minor   bigint NOT NULL CHECK (price_minor > 0),
  -- Насколько опция сдвигает срок. Ноль — законное значение: «отдать
  -- исходники» ничего не сдвигает.
  extra_days    int NOT NULL DEFAULT 0 CHECK (extra_days BETWEEN 0 AND 30),
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX service_options_position_key ON service_options (service_id, position);
CREATE INDEX service_options_service_idx ON service_options (service_id);

-- Что именно докупили — снимком, как и комиссия: цена опции завтра может
-- измениться, а сделка вчерашняя.
CREATE TABLE contract_options (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id  uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  name         text NOT NULL,
  price_minor  bigint NOT NULL CHECK (price_minor > 0),
  extra_days   int NOT NULL DEFAULT 0,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX contract_options_contract_idx ON contract_options (contract_id);

-- ── 2. Подтверждение заказа исполнителем ────────────────────────────────────

ALTER TABLE contracts
  ADD COLUMN developer_confirm_deadline timestamptz,
  ADD COLUMN developer_confirmed_at     timestamptz;

COMMENT ON COLUMN contracts.developer_confirm_deadline IS
  'Срок, до которого исполнитель должен принять заказ услуги. NULL у сделок из откликов: там он уже согласился, когда откликался.';

-- Индекс ровно под запрос фоновой задачи и ни подо что больше.
CREATE INDEX contracts_awaiting_confirmation_idx
  ON contracts (developer_confirm_deadline)
  WHERE developer_confirmed_at IS NULL AND developer_confirm_deadline IS NOT NULL;

-- ── 3. Автоприёмка ──────────────────────────────────────────────────────────

ALTER TABLE milestones ADD COLUMN auto_approve_at timestamptz;

COMMENT ON COLUMN milestones.auto_approve_at IS
  'Когда сданная работа будет принята сама, если заказчик промолчит. Ставится при сдаче, снимается при доработке, споре и приёмке.';

CREATE INDEX milestones_auto_approve_idx
  ON milestones (auto_approve_at)
  WHERE status = 'submitted' AND auto_approve_at IS NOT NULL;

-- ── 4. Уровень исполнителя ──────────────────────────────────────────────────

ALTER TABLE developer_profiles
  ADD COLUMN seller_level text NOT NULL DEFAULT 'new'
    CHECK (seller_level IN ('new','advanced','professional')),
  ADD COLUMN seller_level_updated_at timestamptz;

CREATE INDEX developer_profiles_level_idx ON developer_profiles (seller_level)
  WHERE is_searchable;

-- ── Уведомления о новых событиях ────────────────────────────────────────────

ALTER TABLE notifications DROP CONSTRAINT notifications_type_check;
ALTER TABLE notifications ADD CONSTRAINT notifications_type_check
  CHECK (type IN (
    'proposal_received','proposal_accepted','proposal_declined','proposal_shortlisted',
    'project_invitation','project_published','project_recommended',
    'message_received',
    'milestone_submitted','milestone_revision_requested','milestone_approved','milestone_released',
    'milestone_auto_approved',
    'payment_succeeded','payment_failed','payment_refunded',
    'review_received','review_published',
    'github_analysis_complete','github_analysis_failed',
    'contract_started','contract_completed','contract_cancelled',
    'order_awaiting_confirmation','order_confirmed','order_declined','order_expired',
    'dispute_opened','dispute_resolved',
    'account_verified','account_warning','account_suspended',
    'identity_submitted','identity_approved','identity_rejected','identity_resubmit_requested',
    'profile_submitted','profile_approved',
    'seller_level_changed'));

-- ── Настройки площадки ──────────────────────────────────────────────────────
--
-- Комиссия ноль: площадка пока бесплатна. Это настройка, а не константа —
-- включается в панели в тот день, когда решат включить, и уже заключённые
-- сделки не меняются: комиссия в них записана снимком.
INSERT INTO platform_settings (key, value, description, scope) VALUES
  ('platform.fee_basis_points', '0'::jsonb,
   'Комиссия площадки в сотых долях процента. 0 — бесплатно, 1000 — 10%.', 'public'),
  ('contracts.auto_approve_days', '3'::jsonb,
   'Через сколько дней сданная работа принимается сама, если заказчик молчит.', 'public'),
  ('contracts.confirm_hours', '24'::jsonb,
   'Сколько часов у исполнителя есть, чтобы принять заказ услуги.', 'public'),
  ('services.max_new', '10'::jsonb,
   'Сколько услуг может опубликовать исполнитель уровня «Новичок».', 'private'),
  ('services.max_advanced', '25'::jsonb,
   'Сколько услуг может опубликовать «Продвинутый».', 'private'),
  ('services.max_professional', '50'::jsonb,
   'Сколько услуг может опубликовать «Профессионал».', 'private')
ON CONFLICT (key) DO NOTHING;
