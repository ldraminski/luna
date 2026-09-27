// HTML → tytuł, opis i sam tekst (Code node nie ma DOM-u, więc wyrażeniami). Wynik przycięty do 20 000 znaków.
const r = $json; const status = Number(r.statusCode || 0);
const body = typeof r.data === 'string' ? r.data : typeof r.body === 'string' ? r.body : '';
if (status < 200 || status >= 300) return [{ json: { ok: false, error: status ? `Strona odpowiedziała kodem ${status}.` : 'Nie udało się pobrać strony.' } }];
const ctype = String((r.headers || {})['content-type'] || '');
if (ctype && !/text\/html|text\/plain|application\/xhtml/i.test(ctype)) return [{ json: { ok: false, error: 'To nie jest strona HTML (' + ctype.split(';')[0] + ').' } }];
const ent = (s) => s.replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
  .replace(/&#39;|&apos;/g, "'").replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n))).replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16)));
const title = ent(((body.match(/<title[^>]*>([\s\S]*?)<\/title>/i) || [])[1] || '').replace(/\s+/g, ' ').trim()).slice(0, 200);
const desc = ent(((body.match(/<meta[^>]+name=["']description["'][^>]*content=["']([^"']*)/i) || [])[1] || '').trim()).slice(0, 300);
let t = body
  .replace(/<(script|style|noscript|svg|template|iframe|head)[\s\S]*?<\/\1>/gi, ' ')
  .replace(/<(nav|footer)[\s\S]*?<\/\1>/gi, ' ')
  .replace(/<!--[\s\S]*?-->/g, ' ')
  .replace(/<(br|\/p|\/div|\/li|\/h[1-6]|\/tr|\/section|\/article)[^>]*>/gi, '\n')
  .replace(/<[^>]+>/g, ' ');
t = ent(t).replace(/[ \t\f\v]+/g, ' ').replace(/\n\s*\n+/g, '\n').trim();
// Odcisk treści (FNV-1a) — żeby przy cyklicznym sprawdzaniu nie pytać modelu, gdy tekst się nie zmienił.
let h = 0x811c9dc5; for (let i = 0; i < t.length; i++) { h ^= t.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
return [{ json: { ok: true, title, desc, text: t.slice(0, 20000), hash: h.toString(16), length: t.length } }];
