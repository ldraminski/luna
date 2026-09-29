-- 29.09.2026: długie notatki głosowe (spotkania, 10–20 min) przepisywane W TLE, po kolei (Whisper na CPU, ~1/3 czasu nagrania).
-- Nagranie leży tu tylko do przepisania — po sukcesie audio = NULL. Wynik to zwykła rzecz w Lunie (items), link w item_id.
CREATE TABLE IF NOT EXISTS voice_notes (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status      text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'transcribing', 'summarizing', 'done', 'error')),
  audio       bytea,
  mime        text NOT NULL DEFAULT 'audio/webm',
  bytes       int NOT NULL DEFAULT 0,
  duration_s  int NOT NULL DEFAULT 0,
  name        text NOT NULL DEFAULT '',          -- nazwa pliku, gdy wgrane z telefonu
  attempts    int NOT NULL DEFAULT 0,
  item_id     uuid REFERENCES items(id) ON DELETE SET NULL,
  error       text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  started_at  timestamptz,
  finished_at timestamptz,
  seen_at     timestamptz                         -- zamknięte na liście „notatki w obróbce”
);
CREATE INDEX IF NOT EXISTS voice_notes_queue ON voice_notes (created_at) WHERE status IN ('queued', 'transcribing', 'summarizing');
CREATE INDEX IF NOT EXISTS voice_notes_user ON voice_notes (user_id, created_at DESC);
