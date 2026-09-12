-- 0009 files and messaging.
--
-- Storage keys are random and never derived from the uploaded filename, and the
-- declared MIME type is recorded separately from the sniffed one so an upload
-- that lied about itself is visible rather than merely rejected silently.

CREATE TABLE files (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id        uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  storage_key     text NOT NULL UNIQUE,
  bucket          text NOT NULL,
  -- Cosmetic only; used for the download filename, never for routing or typing.
  original_name   text NOT NULL,
  byte_size       bigint NOT NULL CHECK (byte_size > 0),
  -- What the browser claimed vs what the server detected from the magic bytes.
  declared_mime   text NOT NULL,
  detected_mime   text NOT NULL,
  checksum_sha256 bytea NOT NULL,
  width           int,
  height          int,
  -- 'private' needs a signed URL and an authorisation check on every request;
  -- 'public' is CDN-cacheable (profile photos, portfolio covers).
  access          text NOT NULL DEFAULT 'private' CHECK (access IN ('private','public')),
  purpose         text NOT NULL CHECK (purpose IN
                    ('avatar','portfolio','project_attachment','message_attachment',
                     'deliverable','dispute_evidence','service_cover')),
  scan_state      text NOT NULL DEFAULT 'pending'
                    CHECK (scan_state IN ('pending','clean','infected','skipped','error')),
  scan_detail     text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  deleted_at      timestamptz
);
CREATE INDEX files_owner_idx   ON files (owner_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX files_purpose_idx ON files (purpose) WHERE deleted_at IS NULL;

-- Late-bound foreign keys for tables declared before `files` existed.
ALTER TABLE project_attachments ADD CONSTRAINT project_attachments_file_fk
  FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE;
ALTER TABLE deliverables ADD CONSTRAINT deliverables_file_fk
  FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE SET NULL;

-- A conversation is always anchored to work: a project (pre-hire) or a contract
-- (post-hire). There is no free-floating inbox, which is what keeps AVERIX from
-- becoming a messenger.
CREATE TABLE conversations (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id   uuid REFERENCES projects(id) ON DELETE CASCADE,
  contract_id  uuid REFERENCES contracts(id) ON DELETE CASCADE,
  proposal_id  uuid REFERENCES proposals(id) ON DELETE SET NULL,
  subject      text,
  last_message_at timestamptz,
  message_count int NOT NULL DEFAULT 0,
  is_locked    boolean NOT NULL DEFAULT false,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT conversations_anchored CHECK (project_id IS NOT NULL OR contract_id IS NOT NULL)
);
CREATE UNIQUE INDEX conversations_contract_key ON conversations (contract_id) WHERE contract_id IS NOT NULL;
CREATE UNIQUE INDEX conversations_proposal_key ON conversations (proposal_id) WHERE proposal_id IS NOT NULL;
CREATE INDEX conversations_recent_idx ON conversations (last_message_at DESC NULLS LAST);
SELECT attach_touch_trigger('conversations');

CREATE TABLE conversation_participants (
  conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  last_read_at    timestamptz,
  unread_count    int NOT NULL DEFAULT 0,
  muted           boolean NOT NULL DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (conversation_id, user_id)
);
CREATE INDEX conversation_participants_user_idx ON conversation_participants (user_id, unread_count);

CREATE TABLE messages (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  sender_id       uuid REFERENCES users(id) ON DELETE SET NULL,
  -- 'system' carries milestone and contract events into the thread so the
  -- conversation is a complete record without duplicating state.
  kind            text NOT NULL DEFAULT 'text' CHECK (kind IN ('text','code','system','milestone_ref','project_ref')),
  body            text,
  -- For kind='code'.
  code_language   text,
  -- Threaded replies, one level deep.
  reply_to_id     uuid REFERENCES messages(id) ON DELETE SET NULL,
  -- References that render as a card rather than a link.
  milestone_id    uuid REFERENCES milestones(id) ON DELETE SET NULL,
  project_id      uuid REFERENCES projects(id) ON DELETE SET NULL,
  system_event    text,
  system_payload  jsonb,
  edited_at       timestamptz,
  deleted_at      timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  -- A message must say something: prose, code, a reference, or an attachment.
  -- Attachments arrive in the same transaction as the row, so the check is a
  -- deferred constraint trigger rather than a row CHECK (which cannot see them).
  CONSTRAINT messages_body_not_blank CHECK (body IS NULL OR length(btrim(body)) > 0)
);
CREATE INDEX messages_conversation_idx ON messages (conversation_id, created_at DESC);
CREATE INDEX messages_sender_idx ON messages (sender_id, created_at DESC);

CREATE TABLE message_attachments (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  message_id uuid NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  file_id    uuid NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  sort_order int NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX message_attachments_message_idx ON message_attachments (message_id, sort_order);

CREATE TABLE message_receipts (
  message_id uuid NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  read_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (message_id, user_id)
);

CREATE OR REPLACE FUNCTION conversations_on_message() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE conversations
     SET last_message_at = NEW.created_at,
         message_count   = message_count + 1,
         updated_at      = now()
   WHERE id = NEW.conversation_id;

  UPDATE conversation_participants
     SET unread_count = unread_count + 1
   WHERE conversation_id = NEW.conversation_id
     AND (NEW.sender_id IS NULL OR user_id <> NEW.sender_id);
  RETURN NULL;
END;
$$;
CREATE TRIGGER messages_bump_conversation
  AFTER INSERT ON messages FOR EACH ROW EXECUTE FUNCTION conversations_on_message();

CREATE OR REPLACE FUNCTION messages_require_content() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.kind IN ('system','milestone_ref','project_ref') THEN RETURN NEW; END IF;
  IF NEW.deleted_at IS NOT NULL THEN RETURN NEW; END IF;
  IF NEW.body IS NOT NULL AND length(btrim(NEW.body)) > 0 THEN RETURN NEW; END IF;
  IF EXISTS (SELECT 1 FROM message_attachments WHERE message_id = NEW.id) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'a message must carry text or at least one attachment'
    USING ERRCODE = 'check_violation';
END;
$$;
CREATE CONSTRAINT TRIGGER messages_content_required
  AFTER INSERT OR UPDATE OF body, kind ON messages
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION messages_require_content();
