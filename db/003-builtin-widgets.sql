-- Komponenty bazowe (od Sekkei, wariant A). HTML żyje w froncie aplikacji, nie w /opt/oboe/widgets.
INSERT INTO widgets (slug, title, description, builtin) VALUES
  ('reminder-once',      'Przypomnienie jednorazowe', 'Termin + odliczanie, kafel lawendowy', true),
  ('reminder-recurring', 'Przypomnienie cykliczne',   'Co ile + najbliższy termin, kafel miętowy', true),
  ('page-summary',       'Streszczenie strony',       'Akcja: pobierz stronę, streść, zapisz; kafel błękitny', true),
  ('checklist',          'Lista do odhaczenia',       'Pozycje z checkboxami, kafel różowy', true),
  ('note',               'Notatka',                   'Sama treść do zapamiętania, bez terminu', true)
ON CONFLICT (slug) DO NOTHING;
