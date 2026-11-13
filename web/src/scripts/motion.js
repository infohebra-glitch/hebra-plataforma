import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { SplitText } from 'gsap/SplitText';
import Lenis from 'lenis';

gsap.registerPlugin(ScrollTrigger, SplitText);

const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const fine = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

// Scroll suave
let lenis = null;
if (!reduce) {
  lenis = new Lenis({ lerp: 0.1, wheelMultiplier: 1 });
  lenis.on('scroll', ScrollTrigger.update);
  gsap.ticker.add((t) => lenis.raf(t * 1000));
  gsap.ticker.lagSmoothing(0);
  document.querySelectorAll('a[href^="#"]').forEach((a) =>
    a.addEventListener('click', (e) => {
      const id = a.getAttribute('href');
      if (id.length > 1 && document.querySelector(id)) { e.preventDefault(); lenis.scrollTo(id, { offset: -40, duration: 1.4 }); }
    })
  );
}
window.__lenis = lenis;

// Barra de progreso: muestra cuánto queda y, al hacer clic, salta a ese punto
const bar = document.querySelector('[data-progress]');
if (bar) {
  const fillEl = bar.querySelector('i');
  const set = gsap.quickSetter(fillEl, 'scaleX');
  ScrollTrigger.create({ start: 0, end: 'max', onUpdate: (s) => set(s.progress) });
  bar.addEventListener('click', (e) => {
    const p = e.clientX / window.innerWidth;
    const y = p * (document.documentElement.scrollHeight - window.innerHeight);
    lenis ? lenis.scrollTo(y, { duration: 1.6 }) : window.scrollTo({ top: y, behavior: 'smooth' });
  });
}

// La barra de navegación viaja: en la portada empieza arriba y se acomoda abajo al hacer scroll
const dock = document.querySelector('[data-dock]');
if (dock && document.querySelector('[data-hero]') && !reduce && window.matchMedia('(min-width: 1101px)').matches) {
  const lift = () => -(window.innerHeight - dock.offsetHeight - window.innerHeight * 0.028 - 18);
  gsap.fromTo(dock, { y: lift }, {
    y: 0, ease: 'none',
    scrollTrigger: { start: 0, end: () => window.innerHeight * 0.7, scrub: 0.2, invalidateOnRefresh: true },
  });
}

// Menú a pantalla completa
const menuBtn = document.querySelector('[data-menu]');
const overlay = document.querySelector('[data-overlay]');
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

// Cursor: un anillo que sigue al ratón, crece sobre enlaces y muestra una palabra sobre zonas de arrastre
const cursor = document.querySelector('[data-cursor]');
if (cursor && fine && !reduce) {
  const ring = cursor.querySelector('span');
  const xTo = gsap.quickTo(cursor, 'x', { duration: 0.45, ease: 'power3' });
  const yTo = gsap.quickTo(cursor, 'y', { duration: 0.45, ease: 'power3' });
  window.addEventListener('pointermove', (e) => { xTo(e.clientX); yTo(e.clientY); cursor.classList.add('on'); }, { passive: true });
  document.addEventListener('pointerleave', () => cursor.classList.remove('on'));
  window.addEventListener('pointerdown', () => cursor.classList.add('down'), { passive: true });
  window.addEventListener('pointerup', () => cursor.classList.remove('down'), { passive: true });
  window.addEventListener('blur', () => cursor.classList.remove('down', 'on'));
  document.addEventListener('pointerover', (e) => {
    const lab = e.target.closest('[data-cursor-label]');
    const link = e.target.closest('a, button, input[type=range], label, select');
    cursor.classList.toggle('label', !!lab);
    cursor.classList.toggle('link', !lab && !!link);
    ring.textContent = lab ? lab.dataset.cursorLabel : '';
  });
}

// Botones magnéticos
if (fine && !reduce) {
  document.querySelectorAll('[data-magnetic]').forEach((el) => {
    const xTo = gsap.quickTo(el, 'x', { duration: 0.6, ease: 'elastic.out(1, .4)' });
    const yTo = gsap.quickTo(el, 'y', { duration: 0.6, ease: 'elastic.out(1, .4)' });
    el.addEventListener('pointermove', (e) => {
      const r = el.getBoundingClientRect();
      xTo((e.clientX - (r.left + r.width / 2)) * 0.28);
      yTo((e.clientY - (r.top + r.height / 2)) * 0.28);
    });
    el.addEventListener('pointerleave', () => { xTo(0); yTo(0); });
  });
}

// Titulares: cada línea sube desde detrás de una máscara
function lines() {
  const els = document.querySelectorAll('[data-lines], main h2[data-reveal], main .page-head h1');
  els.forEach((el) => {
    el.removeAttribute('data-reveal');
    if (reduce) { el.style.visibility = 'visible'; return; }
    const inHero = !!el.closest('[data-hero]');
    SplitText.create(el, {
      type: 'lines', mask: 'lines', linesClass: 'ln', autoSplit: true,
      onSplit(self) {
        el.style.visibility = 'visible';
        return gsap.from(self.lines, {
          yPercent: 105, duration: inHero ? 1.3 : 1.1, ease: 'expo.out', stagger: 0.1,
          delay: inHero ? 0.25 : 0,
          scrollTrigger: inHero ? undefined : { trigger: el, start: 'top 85%', once: true },
        });
      },
    });
  });
}
if (document.fonts?.status === 'loaded') lines();
else (document.fonts?.ready || Promise.resolve()).then(lines);

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
