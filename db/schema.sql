-- Oboe — schemat startowy (etap 1). Kolejne zmiany jako osobne pliki migracji.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE users (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email         text NOT NULL UNIQUE,
  name          text,
  password_hash text,                 -- NULL gdy konto tylko przez Google
  google_sub    text UNIQUE,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sessions (
  token_hash  text PRIMARY KEY,       -- sha256 tokenu; sam token tylko u klienta
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at  timestamptz NOT NULL DEFAULT now(),
  expires_at  timestamptz NOT NULL
);
CREATE INDEX ON sessions (user_id);

-- Biblioteka widgetów (globalna). HTML w plikach /opt/oboe/widgets/<slug>/v<N>.html, tu metadane.
CREATE TABLE widgets (
  slug           text PRIMARY KEY,
  title          text NOT NULL,
  description    text,
  input_schema   jsonb NOT NULL DEFAULT '{}',   -- jakie dane widget przyjmuje (postMessage)
  active_version int,
  builtin        boolean NOT NULL DEFAULT false, -- komponenty bazowe od Sekkei
  created_by     uuid REFERENCES users(id),
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE widget_versions (
  slug        text NOT NULL REFERENCES widgets(slug) ON DELETE CASCADE,
  version     int  NOT NULL,
  file_path   text NOT NULL,                     -- względem /opt/oboe/widgets
  git_commit  text,
  guardian    text NOT NULL DEFAULT 'pending' CHECK (guardian IN ('pending','approved','rejected')),
  guardian_notes text,
  model       text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (slug, version)
);

-- To, co użytkownik zlecił (jednorazowe, cykliczne, akcja). Elastyczne: szczegóły w spec.
CREATE TABLE items (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind        text NOT NULL,                     -- reminder-once | reminder-recurring | action | checklist | ...
  source_text text NOT NULL,                     -- oryginalne zdanie użytkownika
  title       text NOT NULL,
  spec        jsonb NOT NULL DEFAULT '{}',       -- to, co zrozumiał model (rrule, wyprzedzenie, URL…)
  widget_slug text REFERENCES widgets(slug),
  data        jsonb NOT NULL DEFAULT '{}',       -- dane do wyświetlenia w widgecie
  status      text NOT NULL DEFAULT 'active' CHECK (status IN ('active','done','archived')),
  position    int,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON items (user_id, status);

-- Zaplanowane powiadomienia; harmonogram n8n co minutę bierze zaległe z sent_at IS NULL.
CREATE TABLE notifications (
  id        bigserial PRIMARY KEY,
  item_id   uuid NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  user_id   uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  due_at    timestamptz NOT NULL,
  channels  text[] NOT NULL DEFAULT '{push}',    -- push, email
  title     text NOT NULL,
  body      text,
  sent_at   timestamptz,
  error     text
);
CREATE INDEX ON notifications (due_at) WHERE sent_at IS NULL;

CREATE TABLE push_subscriptions (
  endpoint    text PRIMARY KEY,
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  p256dh      text,
  auth        text,
  user_agent  text,
  created_at  timestamptz NOT NULL DEFAULT now()
);
