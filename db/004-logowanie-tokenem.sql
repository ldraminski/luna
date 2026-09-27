-- Decyzja Łukasza 27.09: bez haseł. Admin wydaje token (mailem albo ręcznie), aplikacja pamięta go na stałe.
-- W bazie tylko sha256 tokenu: zgubiony token = nowy token, stary przestaje działać.
DROP TABLE IF EXISTS login_attempts;
ALTER TABLE users DROP COLUMN IF EXISTS password_hash;
ALTER TABLE sessions ALTER COLUMN expires_at SET DEFAULT 'infinity';
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS last_used_at timestamptz;
DELETE FROM sessions;
