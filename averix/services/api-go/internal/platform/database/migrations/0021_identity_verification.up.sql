-- Проверка личности и точные права администраторов.
--
-- До этой миграции «личность подтверждена» было булевым полем, которое
-- администратор переключал вручную, ничем не подкреплённое: ни документа,
-- ни решения, ни следа о том, кто и на каком основании его поставил.
--
-- Здесь появляется полный случай проверки: что человек прислал, кто это
-- смотрел, что решил и почему. Сами изображения документов не лежат рядом с
-- аватарами и портфолио — у них отдельное приватное хранилище, отдельная
-- таблица и отдельное право доступа, которое не выдаётся ни одной роли
-- автоматически.

-- ── Точечные права администратора ───────────────────────────────────────────
--
-- Роли по-прежнему задают базовый набор прав в коде. Эта таблица добавляет
-- поверх него именные выдачи: право смотреть паспорта не должно появляться у
-- человека просто потому, что ему выдали роль модератора.
CREATE TABLE admin_permission_grants (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  permission  text NOT NULL,
  granted_by  uuid REFERENCES users(id) ON DELETE SET NULL,
  granted_at  timestamptz NOT NULL DEFAULT now(),
  revoked_by  uuid REFERENCES users(id) ON DELETE SET NULL,
  revoked_at  timestamptz,
  note        text,
  CONSTRAINT admin_permission_grants_note_len CHECK (note IS NULL OR length(note) <= 500)
);

-- Одна действующая выдача на право. Отозванные остаются историей.
CREATE UNIQUE INDEX admin_permission_grants_active
  ON admin_permission_grants (user_id, permission) WHERE revoked_at IS NULL;
CREATE INDEX admin_permission_grants_user ON admin_permission_grants (user_id);

-- ── Случай проверки личности ────────────────────────────────────────────────
CREATE TABLE identity_verifications (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status        text NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft','submitted','under_review','resubmit_requested',
                                  'approved','rejected','suspended','expired')),
  document_type text CHECK (document_type IN ('national_id','passport','driver_licence','residence_permit')),
  country_code  char(2),
  -- Имя и дата рождения так, как они написаны в документе: их сверяет
  -- проверяющий. Это персональные данные, они не выходят за пределы
  -- защищённого раздела.
  document_name text CHECK (document_name IS NULL OR length(document_name) <= 200),
  date_of_birth date,
  -- Нужна ли селфи с документом в руках — решает политика площадки.
  selfie_required        boolean NOT NULL DEFAULT true,
  selfie_with_document   boolean NOT NULL DEFAULT false,
  submitted_at  timestamptz,
  reviewed_at   timestamptz,
  reviewed_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  decision_reason text CHECK (decision_reason IS NULL OR length(decision_reason) <= 2000),
  -- Что именно просят переснять: список причин из закрытого набора.
  resubmit_reasons text[] NOT NULL DEFAULT '{}',
  -- Когда удалить исходные изображения, сохранив результат проверки.
  retention_expires_at timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

-- Открытый случай у человека может быть только один: иначе непонятно, какой
-- из них смотрит проверяющий и на какой отвечает заявитель.
CREATE UNIQUE INDEX identity_verifications_open_per_user
  ON identity_verifications (user_id)
  WHERE status IN ('draft','submitted','under_review','resubmit_requested');
CREATE INDEX identity_verifications_user ON identity_verifications (user_id, created_at DESC);
CREATE INDEX identity_verifications_queue
  ON identity_verifications (status, submitted_at)
  WHERE status IN ('submitted','under_review');

-- ── Изображения документов ──────────────────────────────────────────────────
--
-- Хранится только ключ в приватном хранилище. Публичного адреса у этих файлов
-- нет и быть не может: их отдаёт единственный эндпоинт, который сначала
-- спрашивает право, а потом пишет в журнал доступа.
CREATE TABLE identity_documents (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  verification_id uuid NOT NULL REFERENCES identity_verifications(id) ON DELETE CASCADE,
  user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind            text NOT NULL
                  CHECK (kind IN ('front','back','selfie','selfie_with_document')),
  storage_key     text NOT NULL,
  mime            text NOT NULL,
  byte_size       bigint NOT NULL CHECK (byte_size > 0),
  checksum_sha256 text NOT NULL,
  width           int,
  height          int,
  status          text NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','accepted','replaced','deleted')),
  created_at      timestamptz NOT NULL DEFAULT now(),
  deleted_at      timestamptz,
  retention_expires_at timestamptz
);

-- Одно действующее изображение каждого вида в случае; заменённые остаются
-- как история с пометкой 'replaced'.
CREATE UNIQUE INDEX identity_documents_current
  ON identity_documents (verification_id, kind)
  WHERE status IN ('pending','accepted');
CREATE INDEX identity_documents_user ON identity_documents (user_id);
CREATE INDEX identity_documents_retention
  ON identity_documents (retention_expires_at)
  WHERE deleted_at IS NULL AND retention_expires_at IS NOT NULL;

-- ── Решения проверяющих ─────────────────────────────────────────────────────
CREATE TABLE identity_review_actions (
  id              bigserial PRIMARY KEY,
  verification_id uuid NOT NULL REFERENCES identity_verifications(id) ON DELETE CASCADE,
  actor_id        uuid REFERENCES users(id) ON DELETE SET NULL,
  action          text NOT NULL,
  reason          text,
  detail          text,
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX identity_review_actions_case ON identity_review_actions (verification_id, created_at DESC);

-- ── Журнал доступа к чувствительным данным ──────────────────────────────────
--
-- Отдельно от audit_logs: там записываются действия, здесь — просмотры. Тот,
-- кто открыл чужой паспорт и ничего не изменил, не оставил бы следа в журнале
-- действий, а именно этот след и нужен.
CREATE TABLE admin_access_logs (
  id              bigserial PRIMARY KEY,
  actor_id        uuid REFERENCES users(id) ON DELETE SET NULL,
  subject_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  resource_type   text NOT NULL,
  resource_id     text,
  action          text NOT NULL,
  reason          text,
  session_id      uuid,
  ip              inet,
  user_agent      text,
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX admin_access_logs_subject ON admin_access_logs (subject_user_id, created_at DESC);
CREATE INDEX admin_access_logs_actor ON admin_access_logs (actor_id, created_at DESC);

-- ── Телефон и блокировка ────────────────────────────────────────────────────
--
-- Телефон нужен поиску в админке и разбору спорных случаев. Хранится в том
-- виде, в котором его ввёл человек, плюс нормализованная форма для поиска.
ALTER TABLE users ADD COLUMN phone text
  CHECK (phone IS NULL OR length(phone) <= 32);
ALTER TABLE users ADD COLUMN phone_digits text
  GENERATED ALWAYS AS (nullif(regexp_replace(coalesce(phone, ''), '\D', '', 'g'), '')) STORED;
CREATE INDEX users_phone_digits ON users (phone_digits) WHERE phone_digits IS NOT NULL;

-- Блокировка — это не приостановка: приостановленный аккаунт возвращается сам
-- по истечении срока, заблокированный не возвращается, пока его не разблокируют.
ALTER TABLE users DROP CONSTRAINT users_status_check;
ALTER TABLE users ADD CONSTRAINT users_status_check
  CHECK (status IN ('pending','active','suspended','banned','deactivated'));

-- Поиск по частичному совпадению во всех полях, по которым ищет админка.
CREATE INDEX users_full_name_trgm ON users USING gin (full_name gin_trgm_ops);
CREATE INDEX users_email_trgm ON users USING gin ((email::text) gin_trgm_ops);

-- Срок хранения исходных изображений по умолчанию. Ноль означает «хранить,
-- пока не удалят вручную» — но по умолчанию это не ноль: паспорта не должны
-- лежать вечно просто потому, что никто не подумал их удалить.
INSERT INTO platform_settings (key, value, description, scope)
VALUES ('identity.retention_days', '180'::jsonb,
        'Через сколько дней после решения удалять изображения документов, сохраняя результат проверки.',
        'private')
ON CONFLICT (key) DO NOTHING;

INSERT INTO platform_settings (key, value, description, scope)
VALUES ('identity.selfie_with_document', 'false'::jsonb,
        'Требовать селфи с документом в руках, а не просто селфи.',
        'private')
ON CONFLICT (key) DO NOTHING;
