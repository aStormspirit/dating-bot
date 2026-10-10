-- Сессии анонимного чата. Один ряд — один пользователь ВК.
CREATE TABLE IF NOT EXISTS chat_sessions (
    user_id BIGINT PRIMARY KEY,
    phase TEXT NOT NULL CHECK (phase IN ('idle', 'searching', 'chatting')),
    generation INTEGER NOT NULL DEFAULT 0,
    persona JSONB,
    user_gender TEXT,
    user_age INTEGER,
    user_name TEXT,
    user_city TEXT,
    last_reply TEXT,
    preferred_female BOOLEAN,
    blocked BOOLEAN NOT NULL DEFAULT FALSE,
    partner_id BIGINT,
    history JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
