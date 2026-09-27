// Plan do raportu liczony KODEM (model dostaje gotowe fakty): dziś + jutro, a w poniedziałek cały tydzień.
// Występowania cyklicznych jak w aplikacji; zaległe = jednorazowe z terminem w przeszłości (wciąż aktywne); niedokończone listy bez terminu.
const Z = 'Europe/Warsaw';
const DNI = ['poniedziałek', 'wtorek', 'środa', 'czwartek', 'piątek', 'sobota', 'niedziela'];
const MIES = ['stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca', 'lipca', 'sierpnia', 'września', 'października', 'listopada', 'grudnia'];
const dayLabel = (d) => `${DNI[d.weekday - 1]}, ${d.day} ${MIES[d.month - 1]}`;
const STEP = { day: { days: 1 }, week: { weeks: 1 }, month: { months: 1 } };
return $input.all().map(({ json: u }) => {
  const now = DateTime.now().setZone(Z); const today = now.startOf('day');
  const weekly = u.force_weekly === true || now.weekday === 1;
  const nDays = weekly ? 7 : 2; const end = today.plus({ days: nDays });
  const days = Array.from({ length: nDays }, (_, k) => ({ date: today.plus({ days: k }).toISODate(),
    label: k === 0 ? 'Dziś' : k === 1 ? 'Jutro' : dayLabel(today.plus({ days: k })), items: [] }));
  const overdue = []; const lists = [];
  for (const it of u.items || []) {
    const evRaw = it.spec?.event_at || it.next_at;
    const left = (it.lists || []).reduce((a, l) => a + (l?.items || []).filter((x) => !x.done).length, 0);
    const total = (it.lists || []).reduce((a, l) => a + (l?.items || []).length, 0);
    if (!evRaw) { if (left) lists.push({ id: it.id, title: it.title, left, total }); continue; }
    let ev = DateTime.fromISO(new Date(evRaw).toISOString()).setZone(Z);
    const r = it.spec?.recurrence;
    if (!r) {
      if (ev < now) { overdue.push({ id: it.id, title: it.title, when: dayLabel(ev) + ', ' + ev.toFormat('HH:mm') }); continue; }
    }
    for (let i = 0; ev < end && i < 400; i++) {
      if (ev >= today) {
        const k = Math.floor(ev.diff(today, 'days').days);
        if (days[k]) days[k].items.push({ id: it.id, title: it.title, time: ev.toFormat('HH:mm'), recurring: !!r, left, total });
      }
      if (!r || !STEP[r.unit]) break;
      ev = ev.plus(Object.fromEntries(Object.entries(STEP[r.unit]).map(([k, v]) => [k, v * r.every])));
    }
  }
  days.forEach((d) => d.items.sort((a, b) => a.time.localeCompare(b.time)));
  const count = days.reduce((a, d) => a + d.items.length, 0);
  const title = weekly ? `Twój tydzień: ${today.day} ${MIES[today.month - 1]} – ${end.minus({ days: 1 }).day} ${MIES[end.minus({ days: 1 }).month - 1]}`
    : `Plan na dziś — ${dayLabel(today)}`;
  const facts = [`Rodzaj: ${weekly ? 'raport tygodnia' : 'raport dnia (dziś i jutro)'}, teraz ${now.toFormat('yyyy-MM-dd HH:mm')}`,
    ...days.map((d) => `${d.label} (${d.date}): ` + (d.items.length ? d.items.map((x) => `${x.time} ${x.title}${x.total ? ` (lista: ${x.left} z ${x.total} do zrobienia)` : ''}`).join('; ') : 'nic')),
    `Zaległe (po terminie, nieodhaczone): ` + (overdue.length ? overdue.map((x) => `${x.title} (${x.when})`).join('; ') : 'brak'),
    `Listy bez terminu z niezrobionymi punktami: ` + (lists.length ? lists.slice(0, 5).map((x) => `${x.title} (${x.left} z ${x.total})`).join('; ') : 'brak')].join('\n');
  return { json: {
    user_id: u.user_id, kind: weekly ? 'weekly' : 'daily', for_date: today.toISODate(),
    content: { title, kind: weekly ? 'weekly' : 'daily', days, overdue, lists: lists.slice(0, 5), count },
    facts, push_title: weekly ? 'Twój plan na tydzień' : 'Twój plan na dziś',
    fallback: count ? `Masz ${count} ${count === 1 ? 'rzecz' : 'rzeczy'} w planie.` : 'Na razie nic nie masz w planie.',
  } };
});
