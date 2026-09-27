-- 27.09.2026 (decyzja Łukasza): ktoś sam podaje imię i e-mail, Łukasz akceptuje prośbę o dostęp, klucz idzie mailem.
-- Istniejące konto dostaje nowy klucz od razu (stare klucze na innych urządzeniach zostają).
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin boolean NOT NULL DEFAULT false;
UPDATE users SET is_admin = true WHERE email = 'admin@example.com';

CREATE TABLE IF NOT EXISTS access_requests (
  id          bigserial PRIMARY KEY,
  email       text NOT NULL,
  name        text,
  status      text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected')),
  created_at  timestamptz NOT NULL DEFAULT now(),
  decided_at  timestamptz,
  decided_by  uuid REFERENCES users(id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS access_requests_one_pending ON access_requests (email) WHERE status = 'pending';

-- limit próśb (także „zgubiłem klucz”): osobno na e-mail i łącznie — chroni skrzynki i reputację renlab.ovh
CREATE TABLE IF NOT EXISTS access_log (
  email  text NOT NULL,
  at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS access_log_at ON access_log (at);

-- powiadomienie o prośbie nie dotyczy żadnej rzeczy; harmonogram i tak robi LEFT JOIN items
ALTER TABLE notifications ALTER COLUMN item_id DROP NOT NULL;
