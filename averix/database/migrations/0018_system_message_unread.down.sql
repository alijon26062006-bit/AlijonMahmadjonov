-- Restore the 0009 definition, which counted every entry.
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
