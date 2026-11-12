const eur = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });
const num = new Intl.NumberFormat('es-ES');

export function init({ gsap, ScrollTrigger, reduce }) {
  calculator();
  heroLabel(gsap, reduce);
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

// La etiqueta del inicio: «tócala» abre la ficha del móvil
function heroLabel(gsap, reduce) {
  const btn = document.querySelector('[data-tap]');
  const phone = document.querySelector('[data-hero-phone]');
  if (!btn || !phone) return;
  phone.querySelector('[data-tap-close]')?.addEventListener('click', () => { btn.click(); btn.focus(); });
  btn.addEventListener('click', () => {
    const open = btn.getAttribute('aria-expanded') !== 'true';
    btn.setAttribute('aria-expanded', String(open));
    btn.querySelector('span').textContent = open ? 'Cerrar la ficha' : 'Tócala con el móvil';
    phone.hidden = !open;
    if (open && !reduce) gsap.fromTo(phone, { y: 24, opacity: 0, rotate: 2 }, { y: 0, opacity: 1, rotate: 0, duration: 0.6, ease: 'power3.out' });
  });
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
  const root = document.querySelector('[data-ficha]');
  if (!root) return;
  root.querySelectorAll('[data-size]').forEach((b) =>
    b.addEventListener('click', () => {
      root.querySelectorAll('[data-size]').forEach((o) => o.setAttribute('aria-pressed', String(o === b)));
      const msg = root.querySelector('[data-size-msg]');
      msg.textContent = `Hecho. Avisamos a la tienda: cabina 2 pide la talla ${b.dataset.size}.`;
    })
  );
  root.querySelectorAll('[data-why]').forEach((b) =>
    b.addEventListener('click', () => {
      root.querySelectorAll('[data-why]').forEach((o) => o.setAttribute('aria-pressed', String(o === b)));
      root.querySelector('[data-why-msg]').textContent = 'Gracias. No guardamos quién eres, solo el motivo.';
    })
  );
  const where = root.querySelector('[data-where]');
  where?.addEventListener('change', () => root.classList.toggle('en-casa', where.value === 'casa'));
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
