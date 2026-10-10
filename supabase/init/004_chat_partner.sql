-- С кем пользователь сейчас говорит. Пусто, пока идёт поиск или диалога нет.
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS partner_id BIGINT;
