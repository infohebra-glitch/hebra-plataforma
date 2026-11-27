import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const fine = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

// Sin scroll suave ni barra de progreso: el navegador desplaza la página de forma nativa.
const lenis = null;

// Menú a pantalla completa
const menuBtn = document.querySelector('[data-menu]');
const overlay = document.querySelector('[data-overlay]');
if (overlay?.dataset.items && !overlay.children.length) {
  const d = JSON.parse(overlay.dataset.items);
  const a = (href, text, cls) => Object.assign(document.createElement('a'), { href, textContent: text, className: cls || '' });
  const ul = document.createElement('ul');
  d.links.forEach(([h, t]) => { const li = document.createElement('li'); li.append(a(h, t)); ul.append(li); });
  const langsEl = Object.assign(document.createElement('span'), { className: 'dock-langs' });
  d.langs.forEach(([h, t, l, cur]) => { const el = a(h, t); el.hreflang = l; if (cur) el.setAttribute('aria-current', 'true'); langsEl.append(el); });
  const foot = Object.assign(document.createElement('div'), { className: 'overlay-foot' });
  foot.append(langsEl, a(d.demo[0], d.demo[1], 'btn'));
  overlay.append(ul, foot);
}
if (menuBtn && overlay) {
  const items = overlay.querySelectorAll('li a, .overlay-foot > *');
  const label = menuBtn.textContent;
  const open = () => {
    overlay.hidden = false;
    menuBtn.setAttribute('aria-expanded', 'true');
    menuBtn.textContent = menuBtn.dataset.close || label;
    document.documentElement.classList.add('menu-open');
    lenis?.stop();
    if (!reduce) {
      gsap.fromTo(overlay, { clipPath: 'inset(0 0 100% 0)' }, { clipPath: 'inset(0 0 0% 0)', duration: 0.8, ease: 'expo.inOut' });
      gsap.fromTo(items, { yPercent: 120, opacity: 0 }, { yPercent: 0, opacity: 1, duration: 0.9, ease: 'expo.out', stagger: 0.05, delay: 0.3 });
    }
    overlay.querySelector('a')?.focus({ preventScroll: true });
  };
  const close = () => {
    menuBtn.setAttribute('aria-expanded', 'false');
    menuBtn.textContent = label;
    document.documentElement.classList.remove('menu-open');
    lenis?.start();
    if (reduce) { overlay.hidden = true; return; }
    gsap.to(overlay, { clipPath: 'inset(0 0 100% 0)', duration: 0.6, ease: 'expo.inOut', onComplete: () => (overlay.hidden = true) });
  };
  menuBtn.addEventListener('click', () => (menuBtn.getAttribute('aria-expanded') === 'true' ? close() : open()));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !overlay.hidden) { close(); menuBtn.focus(); } });
  overlay.querySelectorAll('a').forEach((a) => a.addEventListener('click', close));
}

// Sin cursor propio, botones magnéticos ni titulares por líneas: menos efectos, más sobrio.

// Revelado discreto, una sola vez por bloque
if (!reduce) {
  gsap.utils.toArray('[data-reveal]').forEach((el) => {
    gsap.to(el, {
      opacity: 1, y: 0, duration: 1.1, ease: 'expo.out',
      scrollTrigger: { trigger: el, start: 'top 88%', once: true },
    });
  });
} else {
  gsap.set('[data-reveal]', { opacity: 1, y: 0 });
}

// El hilo: se cose con el scroll
document.querySelectorAll('[data-thread]').forEach((svg) => {
  const path = svg.querySelector('path');
  if (!path) return;
  const len = path.getTotalLength();
  path.style.strokeDasharray = `${len}`;
  if (reduce) { path.style.strokeDashoffset = '0'; return; }
  path.style.strokeDashoffset = `${len}`;
  gsap.to(path, {
    strokeDashoffset: 0, ease: 'none',
    scrollTrigger: {
      trigger: svg.closest('[data-thread-scope]') || svg,
      start: svg.dataset.start || 'top 70%',
      end: svg.dataset.end || 'bottom 60%',
      scrub: 0.6,
    },
  });
});

window.addEventListener('load', () => ScrollTrigger.refresh());

// Módulos de página
import('./modules.js').then((m) => m.init({ gsap, ScrollTrigger, reduce, lenis, fine }));
