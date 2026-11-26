// Alta a la newsletter: rep el correu des de la web i el dona d'alta a MailerLite amb l'API.
// Necessita la variable d'entorn MAILERLITE_API_KEY a Vercel (Settings → Environment Variables).
const GROUP = '204389141017790234'; // grup «Newsletter web hebraia.com»
const LANGS = ['es', 'ca', 'en'];

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ ok: false });
  let body = req.body || {};
  if (typeof body === 'string') { try { body = JSON.parse(body); } catch { body = {}; } }
  const email = String(body.email || '').trim().toLowerCase();
  const idioma = LANGS.includes(body.idioma) ? body.idioma : 'es';
  if (body.web) return res.status(200).json({ ok: true }); // trampa per a bots
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email) || email.length > 254 || body.consent !== true) {
    return res.status(400).json({ ok: false, error: 'invalid' });
  }
  const key = process.env.MAILERLITE_API_KEY;
  if (!key) return res.status(500).json({ ok: false, error: 'config' });
  try {
    const r = await fetch('https://connect.mailerlite.com/api/subscribers', {
      method: 'POST',
      headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ email, fields: { idioma }, groups: [GROUP], opted_in_at: new Date().toISOString().slice(0, 19).replace('T', ' ') }),
    });
    if (!r.ok) {
      console.error('mailerlite', r.status, (await r.text()).slice(0, 300));
      return res.status(502).json({ ok: false, error: 'upstream' });
    }
    return res.status(200).json({ ok: true });
  } catch (e) {
    console.error('mailerlite', e);
    return res.status(502).json({ ok: false, error: 'network' });
  }
}
