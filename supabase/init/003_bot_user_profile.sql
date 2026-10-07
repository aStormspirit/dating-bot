-- Профиль в уже созданной таблице: ссылка на VK, премиум и число поисков.
ALTER TABLE bot_users
    ADD COLUMN IF NOT EXISTS vk_url TEXT GENERATED ALWAYS AS ('https://vk.com/id' || user_id::text) STORED;

ALTER TABLE bot_users
    ADD COLUMN IF NOT EXISTS is_premium BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE bot_users
    ADD COLUMN IF NOT EXISTS search_count INTEGER NOT NULL DEFAULT 0;

COMMENT ON COLUMN bot_users.vk_url IS 'Ссылка на страницу VK';
COMMENT ON COLUMN bot_users.is_premium IS 'Есть ли премиум';
COMMENT ON COLUMN bot_users.search_count IS 'Сколько раз запускал поиск собеседника';
