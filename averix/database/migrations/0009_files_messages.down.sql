DROP TABLE IF EXISTS message_receipts, message_attachments, messages,
  conversation_participants, conversations;
ALTER TABLE IF EXISTS deliverables DROP CONSTRAINT IF EXISTS deliverables_file_fk;
ALTER TABLE IF EXISTS project_attachments DROP CONSTRAINT IF EXISTS project_attachments_file_fk;
DROP TABLE IF EXISTS files;
DROP FUNCTION IF EXISTS conversations_on_message();
DROP FUNCTION IF EXISTS messages_require_content();
