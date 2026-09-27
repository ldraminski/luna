-- 28.09.2026 (Łukasz): raport dzienny (dziś + jutro) o wybranej godzinie, domyślnie 9:00; w poniedziałek raport tygodnia.
-- Pokazuje się raz dziennie (seen_at), można do niego wrócić z ikony w aplikacji.
ALTER TABLE users ADD COLUMN IF NOT EXISTS report_time time NOT NULL DEFAULT '09:00';
ALTER TABLE users ADD COLUMN IF NOT EXISTS report_enabled boolean NOT NULL DEFAULT true;
CREATE TABLE IF NOT EXISTS reports (
  id          bigserial PRIMARY KEY,
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind        text NOT NULL CHECK (kind IN ('daily', 'weekly')),
  for_date    date NOT NULL,             -- dzień raportu (Europe/Warsaw)
  content     jsonb NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  seen_at     timestamptz,
  UNIQUE (user_id, for_date)
);
