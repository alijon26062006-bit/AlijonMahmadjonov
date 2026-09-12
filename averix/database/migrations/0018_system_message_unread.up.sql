-- 0018 system entries do not create unread badges.
--
-- A milestone event belongs in the thread — that is what makes the workspace
-- conversation a complete record — but it is not someone waiting for a reply.
-- Counting it as unread put a badge on the client's own action the moment they
-- signed the contract, and a badge that appears for something you just did
-- teaches people to ignore badges.
--
-- The contract's own surfaces (progress, "needs my action") carry the state.
-- The unread count stays what it says: messages a person wrote to you.
CREATE OR REPLACE FUNCTION conversations_on_message() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE conversations
     SET last_message_at = NEW.created_at,
         message_count   = message_count + 1,
         updated_at      = now()
   WHERE id = NEW.conversation_id;

  IF NEW.kind = 'system' THEN
    RETURN NULL;
  END IF;

  UPDATE conversation_participants
     SET unread_count = unread_count + 1
   WHERE conversation_id = NEW.conversation_id
     AND (NEW.sender_id IS NULL OR user_id <> NEW.sender_id);
  RETURN NULL;
END;
$$;
