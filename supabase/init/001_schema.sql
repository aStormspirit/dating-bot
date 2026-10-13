-- Схема анонимного чата. Файл идемпотентный: Chat API прогоняет его при каждом старте.
-- Пользователь — тройка (platform, bot_key, user_id): один человек в двух ботах — два адреса.

CREATE TABLE IF NOT EXISTS chat_sessions (
    platform TEXT NOT NULL DEFAULT 'vk',
    bot_key TEXT NOT NULL DEFAULT '',
    user_id BIGINT NOT NULL,
    phase TEXT NOT NULL CHECK (phase IN ('idle', 'searching', 'chatting')),
    partner_platform TEXT,
    partner_bot_key TEXT,
    partner_id BIGINT,
    searching_since TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (platform, bot_key, user_id)
);

CREATE TABLE IF NOT EXISTS bot_users (
    platform TEXT NOT NULL DEFAULT 'vk',
    bot_key TEXT NOT NULL DEFAULT '',
    user_id BIGINT NOT NULL,
    search_count INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (platform, bot_key, user_id)
);

-- Базы, созданные до мультиплатформы: недостающие колонки и составной ключ.
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS platform TEXT NOT NULL DEFAULT 'vk';
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS bot_key TEXT NOT NULL DEFAULT '';
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS partner_platform TEXT;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS partner_bot_key TEXT;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS partner_id BIGINT;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS searching_since TIMESTAMPTZ;

ALTER TABLE bot_users ADD COLUMN IF NOT EXISTS platform TEXT NOT NULL DEFAULT 'vk';
ALTER TABLE bot_users ADD COLUMN IF NOT EXISTS bot_key TEXT NOT NULL DEFAULT '';
ALTER TABLE bot_users ADD COLUMN IF NOT EXISTS search_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE bot_users ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

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

CREATE INDEX IF NOT EXISTS chat_sessions_queue_idx
    ON chat_sessions (searching_since)
    WHERE phase = 'searching' AND searching_since IS NOT NULL;

CREATE INDEX IF NOT EXISTS bot_users_last_seen_idx ON bot_users (last_seen_at);

COMMENT ON COLUMN chat_sessions.partner_id IS 'С кем пользователь сейчас говорит';
COMMENT ON COLUMN chat_sessions.searching_since IS 'Когда пользователь встал в очередь поиска';
COMMENT ON COLUMN bot_users.search_count IS 'Сколько раз запускал поиск собеседника';
COMMENT ON COLUMN bot_users.last_seen_at IS 'Последнее сообщение или поиск: по нему считается онлайн';
COMMENT ON COLUMN chat_sessions.platform IS 'vk, tg, web или engine — аккаунт chat-engine вместо живого собеседника';
