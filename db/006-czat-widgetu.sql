-- Czat „Popraw widget”: rozmowa z AI aż do potwierdzonego projektu, potem przebudowa.
CREATE TABLE IF NOT EXISTS widget_chats (
  id          bigserial PRIMARY KEY,
  item_id     uuid NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  messages    jsonb NOT NULL DEFAULT '[]',          -- [{role: user|assistant, text, at}]
  proposal    jsonb,                                -- gotowy projekt (gdy AI jest pewne)
  status      text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'confirmed', 'closed')),
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS widget_chats_one_open ON widget_chats (item_id) WHERE status = 'open';
