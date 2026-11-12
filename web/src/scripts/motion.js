import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import Lenis from 'lenis';

gsap.registerPlugin(ScrollTrigger);

const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Scroll suave (no si la persona pide menos movimiento)
if (!reduce) {
  const lenis = new Lenis({ lerp: 0.11 });
  lenis.on('scroll', ScrollTrigger.update);
  gsap.ticker.add((t) => lenis.raf(t * 1000));
  gsap.ticker.lagSmoothing(0);
  document.querySelectorAll('a[href^="#"]').forEach((a) =>
    a.addEventListener('click', (e) => {
      const id = a.getAttribute('href');
      if (id.length > 1 && document.querySelector(id)) { e.preventDefault(); lenis.scrollTo(id, { offset: -80 }); }
    })
  );
}

// Cabecera: fondo al bajar, se esconde al bajar rápido y vuelve al subir
const top = document.querySelector('[data-top]');
if (top) {
  let last = 0;
  const onScroll = () => {
    const y = window.scrollY;
    top.classList.toggle('scrolled', y > 20);
    top.classList.toggle('hide', y > 400 && y > last + 4 && !document.querySelector('.nav.open'));
    if (y < last - 4) top.classList.remove('hide');
    last = y;
  };
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
}

// Menú móvil
const menu = document.querySelector('[data-menu]');
const nav = document.getElementById('nav');
menu?.addEventListener('click', () => {
  const open = menu.getAttribute('aria-expanded') !== 'true';
  menu.setAttribute('aria-expanded', String(open));
  nav.classList.toggle('open', open);
});

// Revelado discreto, una sola vez por bloque
if (!reduce) {
  gsap.utils.toArray('[data-reveal]').forEach((el) => {
    gsap.to(el, {
      opacity: 1, y: 0, duration: 0.9, ease: 'power3.out',
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

// Módulos de página
import('./modules.js').then((m) => m.init({ gsap, ScrollTrigger, reduce }));
