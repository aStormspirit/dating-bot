-- Один человек может писать разным ботам ВК и Telegram. Старые ряды остаются за ВК.
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS platform TEXT NOT NULL DEFAULT 'vk';
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS bot_key TEXT NOT NULL DEFAULT '';
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS partner_platform TEXT;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS partner_bot_key TEXT;

ALTER TABLE bot_users ADD COLUMN IF NOT EXISTS platform TEXT NOT NULL DEFAULT 'vk';
ALTER TABLE bot_users ADD COLUMN IF NOT EXISTS bot_key TEXT NOT NULL DEFAULT '';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_index i
    JOIN pg_class c ON c.oid = i.indrelid
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY (i.indkey)
    WHERE c.relname = 'chat_sessions' AND i.indisprimary AND a.attname = 'platform'
  ) THEN
    ALTER TABLE chat_sessions DROP CONSTRAINT chat_sessions_pkey;
    ALTER TABLE chat_sessions ADD PRIMARY KEY (platform, bot_key, user_id);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_index i
    JOIN pg_class c ON c.oid = i.indrelid
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY (i.indkey)
    WHERE c.relname = 'bot_users' AND i.indisprimary AND a.attname = 'platform'
  ) THEN
    ALTER TABLE bot_users DROP CONSTRAINT bot_users_pkey;
    ALTER TABLE bot_users ADD PRIMARY KEY (platform, bot_key, user_id);
  END IF;
END $$;
