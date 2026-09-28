-- 28.09.2026: dzienny limit akcji z modelem dla nowych kont (testerzy z publicznego repo) — jeden klucz OpenRouter dla wszystkich.
-- NULL = bez limitu. Nowe konta dostają domyślnie 20; istniejące konta (sprzed limitu) — bez limitu.
-- Zmiana dla jednej osoby: UPDATE users SET daily_limit = NULL WHERE email = '...';
ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_limit integer;
UPDATE users SET daily_limit = NULL;
ALTER TABLE users ALTER COLUMN daily_limit SET DEFAULT 20;

-- Każda akcja kosztująca wywołanie modelu (dodanie rzeczy, rozbicie materiału, wiadomość w czacie „Popraw”).
CREATE TABLE IF NOT EXISTS usage_log (
  id       bigserial PRIMARY KEY,
  user_id  uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind     text NOT NULL,
  at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS usage_log_user_at ON usage_log (user_id, at);
