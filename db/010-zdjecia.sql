-- 28.09.2026 (Łukasz): miniatura zdjęcia na kafelku. Tylko zmniejszona wersja (≤800 px JPEG, robi ją przeglądarka),
-- w osobnej tabeli, żeby lista rzeczy nie ciągnęła obrazów; dostęp wyłącznie przez API z kluczem właściciela.
CREATE TABLE IF NOT EXISTS item_photos (
  item_id     uuid PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  image       text NOT NULL,          -- data:image/jpeg;base64,…
  created_at  timestamptz NOT NULL DEFAULT now()
);
