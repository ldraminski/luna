-- 28.09.2026: miękkie usunięcie („Cofnij”) — status 'deleted', na dobre po 30 dniach (Harmonogram).
ALTER TABLE items DROP CONSTRAINT IF EXISTS items_status_check;
ALTER TABLE items ADD CONSTRAINT items_status_check CHECK (status IN ('active', 'done', 'archived', 'deleted'));
