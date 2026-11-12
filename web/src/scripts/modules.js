const loc = { es: 'es-ES', ca: 'ca-ES', en: 'en-GB' }[document.documentElement.lang] || 'es-ES';
const eur = new Intl.NumberFormat(loc, { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });
const num = new Intl.NumberFormat(loc);

export function init({ gsap, ScrollTrigger, reduce }) {
  calculator();
  stage(gsap, ScrollTrigger, reduce);
  splitHeads(gsap, reduce);
  demoMode();
  ficha();
  contact();
  simulator(gsap, reduce);
  dataCards();
  videoDemo();
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
    out('conversion').textContent = (root.dataset.of || '{n} / 100').replace('{n}', c);
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
function ficha() {
  document.querySelectorAll('[data-ficha]').forEach(fichaOne);
}
function fichaOne(root) {
  root.querySelectorAll('[data-size]').forEach((b) =>
    b.addEventListener('click', () => {
      root.querySelectorAll('[data-size]').forEach((o) => o.setAttribute('aria-pressed', String(o === b)));
      const msg = root.querySelector('[data-size-msg]');
      msg.textContent = (b.dataset.ok === '0' ? msg.dataset.outMsg : msg.dataset.okMsg).replace('{s}', b.dataset.size);
    })
  );
  root.querySelectorAll('[data-why]').forEach((b) =>
    b.addEventListener('click', () => {
      root.querySelectorAll('[data-why]').forEach((o) => o.setAttribute('aria-pressed', String(o === b)));
      const wm = root.querySelector('[data-why-msg]'); wm.textContent = wm.dataset.msg;
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

// Simulador del probador
export function simulator(gsap, reduce) {
  const root = document.querySelector('[data-sim]');
  if (!root) return;
  const T = JSON.parse(root.querySelector('[data-sim-i18n]').textContent);
  const q = (s) => root.querySelector(s);
  const qa = (s) => [...root.querySelectorAll(s)];
  const garments = qa('[data-g]');
  const hanger = q('[data-hanger]'), empty = q('[data-empty]'), status = q('[data-status]'), timer = q('[data-timer]');
  const choices = q('[data-choices]'), sizePick = q('[data-sizepick]'), whyPick = q('[data-whypick]');
  const seed = () => ({ p: [6, 4, 9, 3], v: [3, 2, 1, 1], sizes: [], reasons: Object.fromEntries(T.reasonList.map((r) => [r, 0])), byG: [{}, {}, {}, {}] });
  let st = seed(), cur = null, busy = false, auto = false;
  st.reasons[T.reasonList[1]] = 3; st.byG[2][T.reasonList[1]] = 3;

  function render(flash) {
    qa('[data-row]').forEach((tr, i) => {
      tr.querySelector('[data-p]').textContent = st.p[i];
      tr.querySelector('[data-v]').textContent = st.v[i];
      const c = st.p[i] ? Math.round((st.v[i] / st.p[i]) * 100) : 0;
      tr.querySelector('[data-bar]').style.width = c + '%';
      tr.querySelector('[data-c]').textContent = st.p[i] ? c + ' %' : '–';
      if (flash === i) { tr.classList.remove('flash'); void tr.offsetWidth; tr.classList.add('flash'); }
    });
    const max = Math.max(1, ...Object.values(st.reasons));
    qa('[data-reason]').forEach((li) => {
      const n = st.reasons[li.dataset.reason] || 0;
      li.querySelector('.sim-bar span').style.width = (n / max) * 100 + '%';
      li.querySelector('b').textContent = n;
    });
    // acción del lunes: la prenda con peor conversión y suficientes pruebas
    let worst = -1, wc = 2;
    st.p.forEach((p, i) => { if (p >= 4) { const c = st.v[i] / p; if (c < wc) { wc = c; worst = i; } } });
    const ins = q('[data-insight]');
    if (worst < 0) { ins.textContent = T.insightEmpty; return; }
    const rs = Object.entries(st.byG[worst]).sort((a, b) => b[1] - a[1]);
    const r = rs.length ? rs[0][0] : Object.entries(st.reasons).sort((a, b) => b[1] - a[1])[0][0];
    ins.textContent = T.insightText.replace('{g}', T.garments[worst]).replace('{p}', st.p[worst]).replace('{v}', st.v[worst]).replace('{vw}', T.saleWord[st.v[worst] === 1 ? 0 : 1]).replace('{r}', r).replace('{fix}', T.fixes[r] || '');
  }

  const wait = (ms) => new Promise((res) => setTimeout(res, reduce ? 0 : ms));

  async function take(i) {
    if (busy) return;
    busy = true; cur = i;
    garments.forEach((b) => b.setAttribute('aria-pressed', String(+b.dataset.g === i)));
    empty.hidden = true; hanger.hidden = false; choices.hidden = true; sizePick.hidden = true; whyPick.hidden = true;
    const path = hanger.querySelector('[data-hanger-path]');
    path.setAttribute('d', garments[i].dataset.icon); path.setAttribute('fill', garments[i].dataset.color);
    status.textContent = T.trying;
    if (!reduce) gsap.fromTo(hanger, { y: -40, opacity: 0, scale: .8 }, { y: 0, opacity: 1, scale: 1, duration: .6, ease: 'back.out(1.6)' });
    timer.style.transition = 'none'; timer.style.width = '0';
    void timer.offsetWidth;
    timer.style.transition = `width ${auto ? 0.5 : 1.6}s linear`; timer.style.width = '100%';
    await wait(auto ? 500 : 1600);
    st.p[i]++; status.textContent = T.counted; render(i);
    busy = false;
    if (!auto) { choices.hidden = false; if (!reduce) gsap.from(choices, { y: 12, opacity: 0, duration: .4 }); }
  }

  function finish() {
    choices.hidden = true; sizePick.hidden = true; whyPick.hidden = true;
    garments.forEach((b) => b.setAttribute('aria-pressed', 'false'));
    if (!reduce) gsap.to(hanger, { y: 30, opacity: 0, duration: .4, onComplete: () => { hanger.hidden = true; empty.hidden = false; gsap.set(hanger, { y: 0, opacity: 1 }); } });
    else { hanger.hidden = true; empty.hidden = false; }
    cur = null;
  }
  function buy(i) { st.v[i]++; render(i); finish(); }
  function size(i, s) {
    st.sizes.push(s);
    const chip = document.createElement('span'); chip.textContent = `${T.garments[i]} · ${s}`;
    const box = q('[data-sizes]'); box.prepend(chip); while (box.children.length > 8) box.lastChild.remove();
    const al = q('[data-alert]'); al.hidden = false; q('[data-alert-text]').textContent = T.alertText.replace('{g}', T.garments[i].toLowerCase()).replace('{s}', s);
    if (!reduce) gsap.fromTo(al, { scale: .96, opacity: 0 }, { scale: 1, opacity: 1, duration: .35 });
    render(); finish();
  }
  function no(i, r) { st.reasons[r] = (st.reasons[r] || 0) + 1; st.byG[i][r] = (st.byG[i][r] || 0) + 1; render(); finish(); }

  garments.forEach((b) => b.addEventListener('click', () => { if (!auto) take(+b.dataset.g); }));
  root.querySelectorAll('[data-act]').forEach((b) => b.addEventListener('click', () => {
    if (cur === null) return;
    const a = b.dataset.act;
    if (a === 'buy') buy(cur);
    if (a === 'size') { sizePick.hidden = false; whyPick.hidden = true; }
    if (a === 'no') { whyPick.hidden = false; sizePick.hidden = true; }
  }));
  root.querySelectorAll('[data-s]').forEach((b) => b.addEventListener('click', () => cur !== null && size(cur, b.dataset.s)));
  root.querySelectorAll('[data-r]').forEach((b) => b.addEventListener('click', () => cur !== null && no(cur, b.dataset.r)));

  // Una tarde entera: 24 pruebas aceleradas, con tendencias realistas por prenda
  const odds = [[.55, .15, .30], [.35, .30, .35], [.12, .08, .80], [.40, .10, .50]];
  const reasonBias = [[1, 1, 2, 1, 1], [5, 2, 1, 1, 1], [1, 6, 2, 1, 1], [1, 1, 3, 1, 2]];
  const pickW = (w) => { const s = w.reduce((a, b) => a + b, 0); let r = Math.random() * s; for (let k = 0; k < w.length; k++) { r -= w[k]; if (r < 0) return k; } return w.length - 1; };
  q('[data-auto]').addEventListener('click', async (e) => {
    if (auto) return;
    auto = true; e.currentTarget.disabled = true;
    for (let n = 0; n < 24; n++) {
      const i = pickW([3, 2, 3, 2]);
      await take(i);
      const o = pickW(odds[i]);
      if (o === 0) buy(i);
      else if (o === 1) size(i, ['S', 'M', 'L', 'XL'][pickW([1, 2, 4, 2])]);
      else no(i, T.reasonList[pickW(reasonBias[i])]);
      await wait(380);
    }
    auto = false; e.currentTarget.disabled = false;
  });
  q('[data-reset]').addEventListener('click', () => {
    if (auto) return;
    st = { p: [0, 0, 0, 0], v: [0, 0, 0, 0], sizes: [], reasons: Object.fromEntries(T.reasonList.map((r) => [r, 0])), byG: [{}, {}, {}, {}] };
    q('[data-sizes]').innerHTML = ''; q('[data-alert]').hidden = true; finish(); render();
  });
  render();
}

// Tarjetas de datos: girar al tocar (en pantallas táctiles)
export function dataCards() {
  document.querySelectorAll('[data-card]').forEach((b) =>
    b.addEventListener('click', () => b.setAttribute('aria-pressed', String(b.getAttribute('aria-pressed') !== 'true')))
  );
}

// Vídeo de demostración: se reproduce al entrar en pantalla y se pausa al salir
export function videoDemo() {
  document.querySelectorAll('[data-video]').forEach((wrap) => {
    const v = wrap.querySelector('video');
    const btn = wrap.querySelector('[data-video-play]');
    if (!v) return;
    btn?.addEventListener('click', () => {
      wrap.classList.add('playing'); v.muted = false; v.controls = true; v.currentTime = 0; v.play();
    });
    new IntersectionObserver(([e]) => {
      if (wrap.classList.contains('playing')) { if (!e.isIntersecting) v.pause(); return; }
      if (e.isIntersecting) v.play().catch(() => {}); else v.pause();
    }, { threshold: 0.35 }).observe(v);
  });
}
