-- Harmonogram powiadomień (n8n co minutę) + push jak w Alertach.
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS shown_at timestamptz;   -- telefon pobrał treść (/api/pending)
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS emailed boolean NOT NULL DEFAULT false;
ALTER TABLE push_subscriptions ADD COLUMN IF NOT EXISTS last_ok_at timestamptz;
ALTER TABLE push_subscriptions ADD COLUMN IF NOT EXISTS last_status int;
ALTER TABLE push_subscriptions ADD COLUMN IF NOT EXISTS failures int NOT NULL DEFAULT 0;

-- Okres powtarzania z spec.recurrence {every, unit: day|week|month}; NULL gdy nie cykliczne.
CREATE OR REPLACE FUNCTION oboe_period(spec jsonb) RETURNS interval LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE spec->'recurrence'->>'unit'
    WHEN 'day'   THEN make_interval(days  => (spec->'recurrence'->>'every')::int)
    WHEN 'week'  THEN make_interval(weeks => (spec->'recurrence'->>'every')::int)
    WHEN 'month' THEN make_interval(months => (spec->'recurrence'->>'every')::int)
  END
$$;
