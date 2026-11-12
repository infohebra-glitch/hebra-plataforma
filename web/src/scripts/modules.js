const eur = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });
const num = new Intl.NumberFormat('es-ES');

export function init({ gsap, ScrollTrigger, reduce }) {
  calculator();
  stage(gsap, ScrollTrigger, reduce);
  splitHeads(gsap, reduce);
  demoMode();
  journey(ScrollTrigger);
  ficha();
  contact();
}

// «¿Cuánto te cuesta tu probador?»
function calculator() {
  const root = document.querySelector('[data-calc]');
  if (!root) return;
  const pr = root.querySelector('[name=pruebas]');
  const cv = root.querySelector('[name=conversion]');
  const pc = root.querySelector('[name=precio]');
  const out = (k) => root.querySelector(`[data-out=${k}]`);
  const update = () => {
    const p = +pr.value, c = +cv.value, e = +pc.value;
    const noVendidas = Math.round(p * (1 - c / 100));
    const semana = noVendidas * e;
    out('pruebas').textContent = num.format(p);
    out('conversion').textContent = `${c} de cada 100`;
    out('precio').textContent = eur.format(e);
    out('semana').textContent = eur.format(semana);
    out('unidades').textContent = num.format(noVendidas);
    out('temporada').textContent = eur.format(semana * 26);
  };
  [pr, cv, pc].forEach((i) => i.addEventListener('input', update));
  update();
}

// Portada: escena 3D fijada; el scroll lleva de la prenda a la etiqueta y al móvil
async function stage(gsap, ScrollTrigger, reduce) {
  const root = document.querySelector('[data-stage]');
  if (!root) return;
  const canvas = root.querySelector('[data-garment]');
  const beats = [...root.querySelectorAll('[data-beat]')];
  const phone = root.querySelector('[data-stage-phone]');
  const bar = root.querySelector('[data-stage-bar]');
  const hint = root.querySelector('[data-stage-hint]');
  const scrim = root.querySelector('[data-stage-scrim]');
  let scene = null;
  try {
    const { mountGarment } = await import('./garment.js');
    scene = mountGarment(canvas, { reduce });
  } catch (e) { canvas.dataset.failed = ''; }
  if (reduce) { if (scene) scene.progress = 0.5; return; }

  // entrada inicial
  gsap.from(canvas, { opacity: 0, duration: 1.6, ease: 'power2.out' });

  const tl = gsap.timeline({ defaults: { ease: 'power2.inOut' }, paused: true });
  tl.to(beats[0], { autoAlpha: 0, y: -40, duration: 0.12 }, 0.2)
    .fromTo(beats[1], { autoAlpha: 0, y: 40 }, { autoAlpha: 1, y: 0, duration: 0.12 }, 0.3)
    .to(beats[1], { autoAlpha: 0, y: -40, duration: 0.1 }, 0.58)
    .fromTo(beats[2], { autoAlpha: 0, y: 40 }, { autoAlpha: 1, y: 0, duration: 0.12 }, 0.68)
    .fromTo(phone, { autoAlpha: 0, y: 120, rotate: 6, scale: 0.92 }, { autoAlpha: 1, y: 0, rotate: 0, scale: 1, duration: 0.2, ease: 'power3.out' }, 0.66)
    .to(hint, { autoAlpha: 0, duration: 0.05 }, 0.04)
    .to(scrim, { opacity: 1, duration: 0.15 }, 0.55)
    .to({}, { duration: 0.1 }, 0.9);

  ScrollTrigger.create({
    trigger: root, start: 'top top', end: 'bottom bottom', scrub: 0.8,
    onUpdate: (self) => {
      const p = self.progress;
      if (scene) scene.progress = p;
      tl.progress(p);
      if (bar) bar.style.transform = `scaleX(${p})`;
      beats.forEach((b, i) => b.setAttribute('aria-hidden', String(i !== (p < 0.28 ? 0 : p < 0.63 ? 1 : 2))));
    },
  });
}

// Titulares que entran palabra a palabra
function splitHeads(gsap, reduce) {
  const all = document.querySelectorAll('[data-split]');
  if (reduce) { all.forEach((el) => (el.style.visibility = 'visible')); return; }
  all.forEach((el) => {
    const words = el.textContent.trim().split(/\s+/);
    el.setAttribute('aria-label', el.textContent.trim());
    el.innerHTML = words.map((w) => `<span class="w" aria-hidden="true"><span>${w}</span></span>`).join(' ');
    const inner = el.querySelectorAll('.w > span');
    el.style.visibility = 'visible';
    const vars = { yPercent: 110, duration: 1, ease: 'power4.out', stagger: 0.06 };
    if (el.closest('[data-stage]')) gsap.from(inner, { ...vars, delay: 0.25 });
    else gsap.from(inner, { ...vars, scrollTrigger: { trigger: el, start: 'top 85%', once: true } });
  });
}

// Página de la ficha: «En la cabina» / «En casa»
function demoMode() {
  const seg = document.querySelector('[data-mode]');
  if (!seg) return;
  const targets = document.querySelectorAll('[data-mode-target]');
  const texts = document.querySelectorAll('[data-mode-text]');
  seg.querySelectorAll('button').forEach((b) =>
    b.addEventListener('click', () => {
      const casa = b.dataset.value === 'casa';
      seg.querySelectorAll('button').forEach((o) => o.setAttribute('aria-pressed', String(o === b)));
      targets.forEach((t) => t.classList.toggle('en-casa', casa));
      texts.forEach((t) => (t.hidden = t.dataset.modeText !== b.dataset.value));
    })
  );
}

// Recorrido en 6 pasos: el plano se ilumina según el paso que se lee
function journey(ScrollTrigger) {
  const root = document.querySelector('[data-journey]');
  if (!root) return;
  const plan = root.querySelector('[data-plan]');
  root.querySelectorAll('[data-step]').forEach((li) => {
    ScrollTrigger.create({
      trigger: li, start: 'top 55%', end: 'bottom 55%',
      onToggle: (self) => {
        if (!self.isActive) return;
        plan.dataset.active = li.dataset.step;
        root.querySelectorAll('[data-step]').forEach((o) => o.classList.toggle('on', o === li));
      },
    });
  });
}

// Ficha NFC de ejemplo
function ficha() {
  document.querySelectorAll('[data-ficha]').forEach(fichaOne);
}
function fichaOne(root) {
  root.querySelectorAll('[data-size]').forEach((b) =>
    b.addEventListener('click', () => {
      root.querySelectorAll('[data-size]').forEach((o) => o.setAttribute('aria-pressed', String(o === b)));
      const msg = root.querySelector('[data-size-msg]');
      msg.textContent = `Hecho. Avisamos a la tienda: te llevamos la ${b.dataset.size} a la cabina 2.`;
    })
  );
  root.querySelectorAll('[data-why]').forEach((b) =>
    b.addEventListener('click', () => {
      root.querySelectorAll('[data-why]').forEach((o) => o.setAttribute('aria-pressed', String(o === b)));
      root.querySelector('[data-why-msg]').textContent = 'Gracias. No guardamos quién eres, solo el motivo.';
    })
  );
}

// Contacto: preselecciona el motivo desde la URL
function contact() {
  const sel = document.querySelector('[name=motivo]');
  if (!sel) return;
  const m = new URLSearchParams(location.search).get('motivo');
  if (m && sel.querySelector(`option[value="${m}"]`)) sel.value = m;
  const sync = () => document.querySelectorAll('[data-marca-only]').forEach((el) => (el.hidden = !['demo', 'piloto'].includes(sel.value)));
  sel.addEventListener('change', sync);
  sync();
}
