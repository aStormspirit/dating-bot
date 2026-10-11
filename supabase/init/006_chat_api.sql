-- Chat API: очередь поиска в базе и гости сайта.
-- Поиск, начатый старым ботом, остаётся без searching_since и в подбор пары не попадает.
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS searching_since TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS chat_sessions_queue_idx
    ON chat_sessions (searching_since)
    WHERE phase = 'searching' AND searching_since IS NOT NULL;

CREATE SEQUENCE IF NOT EXISTS web_guest_id_seq;

COMMENT ON COLUMN chat_sessions.searching_since IS 'Когда пользователь встал в очередь поиска';
