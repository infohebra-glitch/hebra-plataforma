"""Converteix els textos legals (markdown) en vistes Astro per a la web d'Hebra."""
import html, json, re, sys
from pathlib import Path

SRC = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('/mnt/project-files/web/legal')
OUT = Path(sys.argv[1])  # web/src/views

EMAIL_PH = ['[CORREU DE CONTACTE]', '[CORREU DE PRIVACITAT]', '[CORREO DE CONTACTO]',
            '[CORREO DE PRIVACIDAD]', '[CONTACT EMAIL]', '[PRIVACY EMAIL]']

PAGES = {  # número de secció -> (vista, ruta, títols, descripcions)
    1: ('AvisoLegal', '/aviso-legal/',
        {'es': 'Aviso legal', 'ca': 'Avís legal', 'en': 'Legal notice'},
        {'es': 'Quién es el titular de hebraia.com y en qué condiciones se puede usar la web.',
         'ca': 'Qui és el titular de hebraia.com i en quines condicions es pot fer servir la web.',
         'en': 'Who owns hebraia.com and the terms for using the website.'}),
    2: ('Privacidad', '/privacidad/',
        {'es': 'Política de privacidad', 'ca': 'Política de privacitat', 'en': 'Privacy policy'},
        {'es': 'Qué datos trata Hebra en la web y en las tiendas, qué no capta nunca y cómo ejercer tus derechos.',
         'ca': 'Quines dades tracta Hebra a la web i a les botigues, què no capta mai i com exercir els teus drets.',
         'en': 'What data Hebra handles on the website and in stores, what it never collects and how to exercise your rights.'}),
    3: ('Cookies', '/cookies/',
        {'es': 'Política de cookies', 'ca': 'Política de galetes', 'en': 'Cookie policy'},
        {'es': 'hebraia.com no usa cookies. Qué medimos y cómo, sin guardar nada en tu dispositivo.',
         'ca': 'hebraia.com no fa servir galetes. Què mesurem i com, sense desar res al teu dispositiu.',
         'en': 'hebraia.com uses no cookies. What we measure and how, without storing anything on your device.'}),
    4: ('PrivacidadFicha', '/privacidad-ficha/',
        {'es': 'Privacidad de la ficha', 'ca': 'Privacitat de la fitxa', 'en': 'Garment page privacy'},
        {'es': 'Qué se registra cuando acercas el móvil a la etiqueta de una prenda, y qué no.',
         'ca': 'Què es registra quan acostes el mòbil a l’etiqueta d’una peça, i què no.',
         'en': 'What is recorded when you hold your phone to a garment label, and what is not.'}),
}


def inline(s: str) -> str:
    for ph in EMAIL_PH:
        s = s.replace(ph, '\x00EMAIL\x00')
    s = html.escape(s, quote=False)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)',
               lambda m: f'<a class="textlink" href="{m.group(2)}"{" rel=\"noopener\"" if m.group(2).startswith("http") else ""}>{m.group(1)}</a>', s)
    s = re.sub(r'\[([^\]]*)\]', lambda m: f'<span class="pend">[{m.group(1)}]</span>', s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)', r'<em>\1</em>', s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    return s.replace('\x00EMAIL\x00', '__EMAIL__')


def render(lines):
    out, i = [], 0
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln or ln == '---':
            i += 1; continue
        if ln.startswith('### '):
            out.append(f'<h2>{inline(ln[4:])}</h2>'); i += 1; continue
        if ln.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(set(c) <= set('-: ') for c in cells):
                    rows.append(cells)
                i += 1
            head, body = rows[0], rows[1:]
            t = '<div class="ltable"><table><thead><tr>' + ''.join(f'<th>{inline(c)}</th>' for c in head) + '</tr></thead><tbody>'
            t += ''.join('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in r) + '</tr>' for r in body)
            out.append(t + '</tbody></table></div>'); continue
        m = re.match(r'^(- |\d+\. )', ln)
        if m:
            tag = 'ul' if ln.startswith('- ') else 'ol'
            items = []
            while i < len(lines) and re.match(r'^(- |\d+\. )', lines[i]):
                items.append(re.sub(r'^(- |\d+\. )', '', lines[i].rstrip())); i += 1
            out.append(f'<{tag}>' + ''.join(f'<li>{inline(x)}</li>' for x in items) + f'</{tag}>'); continue
        para = []
        while i < len(lines) and lines[i].strip() and not re.match(r'^(### |\||- |\d+\. |---)', lines[i]):
            para.append(lines[i].strip()); i += 1
        text = ' '.join(para)
        if text.startswith('*(') and text.endswith(')*'):  # nota interna per a l'equip
            out.append(f'<p><span class="pend">{inline(text[2:-2])}</span></p>'); continue
        if re.match(r'^\*(Última|Darrera|Last) ', text):
            out.append(f'<p class="quiet">{inline(text.strip("*"))}</p>'); continue
        if text.startswith('*'):  # descripció interna de la pàgina: no es publica
            continue
        out.append(f'<p>{inline(text)}</p>')
    return '\n'.join(out)


def sections(lang):
    txt = (SRC / f'textos-legals-{lang}.md').read_text()
    parts = re.split(r'^## (\d+)\. .*$', txt, flags=re.M)
    return {int(parts[k]): parts[k + 1].splitlines() for k in range(1, len(parts), 2)}


secs = {l: sections(l) for l in ('es', 'ca', 'en')}
for n, (view, route, titles, descs) in PAGES.items():
    data = {l: {'title': titles[l], 'description': descs[l], 'html': render(secs[l][n])} for l in secs}
    src = f"""---
// Generat a partir de /mnt/project-files/web/legal/textos-legals-*.md (no editar a mà: canviar el markdown i regenerar).
import Legal from '../components/Legal.astro';
import {{ mainEmail, type Lang }} from '../i18n';
interface Props {{ lang: Lang }}
const {{ lang }} = Astro.props;
const T = {json.dumps(data, ensure_ascii=False, indent=1)} as const;
const email = `<a class="textlink" href="mailto:${{mainEmail}}">${{mainEmail}}</a>`;
const body = T[lang].html.replaceAll('__EMAIL__', email);
---
<Legal lang={{lang}} route="{route}" title={{T[lang].title}} description={{T[lang].description}}>
  <Fragment set:html={{body}} />
</Legal>
"""
    (OUT / f'{view}.astro').write_text(src)
    print(view, {l: len(d['html']) for l, d in data.items()})
