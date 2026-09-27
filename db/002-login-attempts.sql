-- Ochrona przed zgadywaniem haseł: max 10 nieudanych prób na e-mail w 15 min.
CREATE TABLE IF NOT EXISTS login_attempts (
  id         bigserial PRIMARY KEY,
  email      text NOT NULL,
  ok         boolean NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS login_attempts_email_time ON login_attempts (email, created_at);
