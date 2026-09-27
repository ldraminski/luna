// Automatyczny skan kodu widgetu PRZED guardianem. Twarde reguły — każde trafienie = odrzucenie.
const raw = String($json.choices?.[0]?.message?.content || '');
const html = raw.replace(/^[\s\S]*?(?=<!doctype html)/i, '').replace(/```\s*$/g, '').trim();
const v = [];
if (!/^<!doctype html/i.test(html)) v.push('brak <!doctype html> — model nie oddał samego kodu');
if (html.length > 60000) v.push('plik większy niż 60 KB');
const BAN = [
  [/\bfetch\s*\(/, 'fetch'], [/XMLHttpRequest/, 'XMLHttpRequest'], [/WebSocket/, 'WebSocket'], [/EventSource/, 'EventSource'],
  [/sendBeacon/, 'sendBeacon'], [/\beval\s*\(/, 'eval'], [/new\s+Function\b/, 'new Function'], [/\bimport\s*\(/, 'import()'],
  [/<\s*iframe/i, '<iframe>'], [/<\s*form\b/i, '<form>'], [/<\s*(object|embed)\b/i, '<object>/<embed>'],
  [/document\s*\.\s*cookie/, 'document.cookie'], [/localStorage|sessionStorage|indexedDB/, 'pamięć przeglądarki'],
  [/window\s*\.\s*(top|opener)\b|\btop\s*\.\s*location|parent\s*\.\s*(document|location|window)/, 'dostęp do okna rodzica'],
  [/<\s*script[^>]*\bsrc\s*=/i, 'zewnętrzny skrypt'], [/\bfromCharCode\b|\batob\s*\(/, 'zaciemnianie (atob/fromCharCode)'],
  [/\[\s*['"`][a-z]+['"`]\s*\+\s*['"`]/i, 'składanie nazw właściwości z kawałków'],
];
for (const [re, name] of BAN) if (re.test(html)) v.push('zakazane: ' + name);
// Zewnętrzne adresy: wolno tylko fonty Google.
for (const m of html.matchAll(/(?:https?:)?\/\/([a-z0-9.-]+\.[a-z]{2,})/gi)) {
  if (!['fonts.googleapis.com', 'fonts.gstatic.com', 'www.w3.org'].includes(m[1].toLowerCase())) v.push('zewnętrzny adres: ' + m[1]);
}
if (!/oboe:data/.test(html)) v.push('nie obsługuje oboe:data');
if (!/oboe:resize/.test(html)) v.push('nie wysyła oboe:resize');
return [{ json: { html, violations: [...new Set(v)] } }];
