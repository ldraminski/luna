-- Specyfikacja każdej wersji — czat poprawek i programista wiedzą, jak widget miał działać.
ALTER TABLE widget_versions ADD COLUMN IF NOT EXISTS spec text;
ALTER TABLE widget_versions ADD COLUMN IF NOT EXISTS item_id uuid;
