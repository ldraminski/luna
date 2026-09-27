-- 27.09.2026 (decyzja Łukasza): rzecz może mieć kilka list z nazwami (np. druga lista na prośbę w „Popraw”).
-- data.checklist + data.checklist_reset → data.lists = [{name, items: [{text, done}], reset}]
UPDATE items SET data = (data - 'checklist' - 'checklist_reset') || jsonb_build_object('lists', jsonb_build_array(
    jsonb_build_object('name', NULL, 'items', data->'checklist', 'reset', coalesce((data->>'checklist_reset')::boolean, false))))
  WHERE jsonb_typeof(data->'checklist') = 'array' AND jsonb_array_length(data->'checklist') > 0;
UPDATE items SET data = data - 'checklist' - 'checklist_reset' WHERE data ? 'checklist' OR data ? 'checklist_reset';
