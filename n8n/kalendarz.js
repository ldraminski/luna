// Model źle liczy daty ("za 3 dni", "w piątek"), więc dostaje gotowy kalendarz liczony tutaj (Luxon, strefa workflow = Europe/Warsaw).
const DNI = ['poniedziałek', 'wtorek', 'środa', 'czwartek', 'piątek', 'sobota', 'niedziela'];
const now = $now.setZone('Europe/Warsaw');
const lines = [];
for (let i = 0; i < 35; i++) {
  const d = now.plus({ days: i });
  const label = i === 0 ? 'dziś' : i === 1 ? 'jutro' : i === 2 ? 'pojutrze' : `za ${i} dni`;
  lines.push(`${d.toFormat('yyyy-MM-dd')} ${DNI[d.weekday - 1]} (${label}), przesunięcie ${d.set({ hour: 12 }).toFormat('ZZ')}`);
}
return [{ json: {
  teraz: `${now.toFormat('yyyy-MM-dd HH:mm')} (${DNI[now.weekday - 1]}), strefa Europe/Warsaw, przesunięcie ${now.toFormat('ZZ')}`,
  kalendarz: lines.join('\n'),
} }];
