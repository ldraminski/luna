-- 30.09.2026: dzienny limit dla nowych kont 20 → 40 (decyzja Łukasza przed postem na LinkedIn — nowi testerzy).
-- Konta, które miały domyślne 20, dostają 40; konta bez limitu (NULL) i z ręcznie ustawioną inną wartością — bez zmian.
ALTER TABLE users ALTER COLUMN daily_limit SET DEFAULT 40;
UPDATE users SET daily_limit = 40 WHERE daily_limit = 20;
