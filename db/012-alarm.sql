-- 28.09.2026 (Łukasz): alarm w chwili terminu — czerwona karta + push co 20 s, dopóki użytkownik nie przełoży / wyłączy / odhaczy.
-- Stan alarmu w items.data.alarm = {state: 'ringing'|'snoozed'|'off', next_at, started_at, count}. Rodzaj powiadomienia — żeby
-- telefon nie układał 180 powiadomień w stos (alarm = jeden, podmieniany).
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS kind text NOT NULL DEFAULT 'reminder';
