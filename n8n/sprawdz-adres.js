// Ochrona przed SSRF: adres podaje użytkownik, a pobiera nasz serwer. Wpuszczamy tylko http(s) na publiczne IP.
// Odpowiedzi DNS (DoH Cloudflare, A i AAAA) przychodzą z dwóch węzłów HTTP przed tym.
const url = $('Adres do pobrania').first().json.url;
const answers = [];
for (const it of $input.all()) for (const a of (it.json.Answer || [])) if (a.type === 1 || a.type === 28) answers.push(String(a.data));
const priv4 = (ip) => {
  const p = ip.split('.').map(Number); if (p.length !== 4 || p.some((x) => !(x >= 0 && x <= 255))) return true;
  return p[0] === 10 || p[0] === 127 || p[0] === 0 || (p[0] === 169 && p[1] === 254) || (p[0] === 172 && p[1] >= 16 && p[1] <= 31)
    || (p[0] === 192 && p[1] === 168) || (p[0] === 100 && p[1] >= 64 && p[1] <= 127) || p[0] >= 224;
};
const priv6 = (ip) => { const s = ip.toLowerCase(); return s === '::1' || s === '::' || /^(fc|fd|fe8|fe9|fea|feb)/.test(s) || s.startsWith('::ffff:'); };
const ips = answers.filter((a) => /^[\d.]+$/.test(a) || a.includes(':'));
if (!ips.length) return [{ json: { ok: false, url, error: 'Nie znalazłem tej domeny (DNS).' } }];
const bad = ips.filter((ip) => (ip.includes(':') ? priv6(ip) : priv4(ip)));
if (bad.length) return [{ json: { ok: false, url, error: 'Ten adres prowadzi do sieci wewnętrznej — nie pobieram go.' } }];
return [{ json: { ok: true, url, ips } }];
