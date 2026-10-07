-- Пользователи, которые написали боту. Ряд не удаляется вместе с диалогом.
CREATE TABLE IF NOT EXISTS bot_users (
    user_id BIGINT PRIMARY KEY,
    gender TEXT CHECK (gender IS NULL OR gender IN ('male', 'female')),
    age INTEGER CHECK (age IS NULL OR age BETWEEN 18 AND 99),
    partner_gender TEXT CHECK (partner_gender IS NULL OR partner_gender IN ('female', 'male', 'any')),
    vk_url TEXT GENERATED ALWAYS AS ('https://vk.com/id' || user_id::text) STORED,
    is_premium BOOLEAN NOT NULL DEFAULT FALSE,
    search_count INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
