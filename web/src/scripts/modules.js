const loc = { es: 'es-ES', ca: 'ca-ES', en: 'en-GB' }[document.documentElement.lang] || 'es-ES';
const eur = new Intl.NumberFormat(loc, { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });
const num = new Intl.NumberFormat(loc);

export function init({ gsap, ScrollTrigger, reduce, lenis, fine }) {
  calculator();
  hero(gsap, ScrollTrigger, reduce);
  words(reduce);
  film(gsap, reduce);
  wipe(gsap, reduce);
  processPin(gsap, ScrollTrigger, reduce);
  fan(gsap, reduce);
  marquee(gsap, reduce);
  explore(gsap, fine, reduce);
  orb(gsap, reduce);
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
    [pr, cv, pc].forEach((i) => i.style.setProperty('--p', ((i.value - i.min) / (i.max - i.min)) * 100 + '%'));
    dots.forEach((d, k) => d.classList.toggle('s', k < c));
  };
  const dots = [...root.querySelectorAll('[data-dots] i')];
  [pr, cv, pc].forEach((i) => i.addEventListener('input', update));
  update();
}

// Portada: escena 3D fijada; el scroll lleva de la prenda a la etiqueta y al móvil
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
  root.querySelectorAll('[data-pair]').forEach((b) => b.addEventListener('click', () => {
    if (b.getAttribute('aria-pressed') === 'true') return;
    b.setAttribute('aria-pressed', 'true');
    b.textContent = '✓ ' + b.dataset.done;
  }));
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

// Portada: visor 3D, píldoras de prenda y ficha que aparece al tocar la etiqueta
async function hero(gsap, ScrollTrigger, reduce) {
  const root = document.querySelector('[data-hero]');
  if (!root) return;
  const box = root.querySelector('[data-viewer]');
  const pills = [...root.querySelectorAll('[data-garment-pick]')];
  const pop = root.querySelector('[data-ficha-pop]');
  const data = JSON.parse(root.querySelector('[data-ficha-data]').textContent);
  const ins = root.querySelectorAll('[data-hero-in]');
  let key = pills[0]?.dataset.garmentPick || 'samarreta';

  if (!reduce) {
    gsap.from(ins, { y: 24, opacity: 0, duration: 1.2, ease: 'expo.out', stagger: 0.08, delay: 0.7 });
    gsap.from(box, { opacity: 0, scale: 0.94, duration: 2, ease: 'expo.out', delay: 0.2 });
    gsap.from(root.querySelector('.hero-glow'), { opacity: 0, scale: 0.6, duration: 2.4, ease: 'expo.out' });
  }

  function showPop() {
    const [h, ...l] = data[key];
    pop.querySelector('[data-fp-h]').textContent = h;
    pop.querySelector('[data-fp-l]').innerHTML = l.map((x) => `<li>${x}</li>`).join('');
    pop.hidden = false;
    if (!reduce) gsap.fromTo(pop, { opacity: 0, y: 20, scale: 0.96 }, { opacity: 1, y: 0, scale: 1, duration: 0.8, ease: 'expo.out' });
    clearTimeout(showPop.t);
    showPop.t = setTimeout(() => hidePop(), 6000);
  }

  const hidePop = () => {
    if (pop.hidden) return;
    if (reduce) { pop.hidden = true; return; }
    gsap.to(pop, { opacity: 0, y: 10, duration: 0.4, onComplete: () => (pop.hidden = true) });
  };

  const fb = root.querySelector('[data-fallback]');
  const fbImg = fb.querySelector('img');
  const fbSrc = (k) => fbImg.src.replace(/[^/]+\.webp$/, k + '.webp');
  const fail = () => { box.dataset.failed = ''; fbImg.src = fbSrc(key); };
  fb.addEventListener('click', showPop);
  pop.querySelector('[data-fp-close]').addEventListener('click', hidePop);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hidePop(); });

  const saveData = navigator.connection?.saveData;
  let viewer = null;
  if (!saveData) {
    try {
      const { mountViewer } = await import('./viewer.js');
      viewer = mountViewer(box, { reduce, onTap: showPop, onFail: fail, onReady: () => delete box.dataset.failed });
    } catch (e) { viewer = null; }
  }
  if (!viewer) fail();
  else {
    viewer.show(key);
    // si en 9 s no hay prenda, se enseña la imagen fija
    setTimeout(() => { if (box.dataset.loading !== undefined) fail(); }, 9000);
    const idle = window.requestIdleCallback || ((f) => setTimeout(f, 2500));
    idle(() => viewer.preload(pills.map((p) => p.dataset.garmentPick)));
    if (!reduce) ScrollTrigger.create({ trigger: root, start: 'top top', end: 'bottom top', onUpdate: (s) => (viewer.scroll = s.progress) });
  }
  pills.forEach((b) => b.addEventListener('click', () => {
    key = b.dataset.garmentPick;
    pills.forEach((o) => o.setAttribute('aria-pressed', String(o === b)));
    hidePop();
    if (box.dataset.failed !== undefined) {
      if (!reduce) gsap.fromTo(fbImg, { opacity: 0, scale: 0.94 }, { opacity: 1, scale: 1, duration: 0.8, ease: 'expo.out' });
      fbImg.src = fbSrc(key);
    }
    viewer?.show(key);
  }));
  // teclado: flechas giran, Intro toca la etiqueta
  const canvas = box.querySelector('canvas');
  canvas.tabIndex = 0;
  canvas.addEventListener('keydown', (e) => {
    if (!viewer) return;
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.preventDefault(); viewer.nudge(e.key === 'ArrowLeft' ? -1 : 1); }
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); viewer.tap(); }
  });
}

// Manifiesto: una palabra clave se ilumina cada poco, al azar
function words(reduce) {
  const root = document.querySelector('[data-words]');
  if (!root) return;
  const ws = [...root.querySelectorAll('[data-w]')];
  let i = 0, timer = null;
  const step = () => {
    ws.forEach((w) => w.classList.remove('on'));
    let n; do { n = Math.floor(Math.random() * ws.length); } while (n === i && ws.length > 1);
    i = n; ws[i].classList.add('on');
  };
  if (reduce) { ws[0].classList.add('on'); return; }
  new IntersectionObserver(([e]) => {
    clearInterval(timer);
    if (e.isIntersecting) { step(); timer = setInterval(step, 1500); }
  }).observe(root);
}

// Vídeo a sangre: al entrar se abre hasta ocupar toda la pantalla
function film(gsap, reduce) {
  const f = document.querySelector('[data-film-frame]');
  if (!f) return;
  const v = f.querySelector('video');
  new IntersectionObserver(([e]) => (e.isIntersecting ? v.play().catch(() => {}) : v.pause())).observe(f);
  if (reduce) { f.style.clipPath = 'none'; return; }
  gsap.fromTo(f, { clipPath: 'inset(9% 14% 9% 14% round 28px)' }, {
    clipPath: 'inset(0% 0% 0% 0% round 0px)', ease: 'none',
    scrollTrigger: { trigger: f, start: 'top 95%', end: 'top 5%', scrub: 0.4 },
  });
  gsap.fromTo(v, { scale: 1.25 }, { scale: 1, ease: 'none', scrollTrigger: { trigger: f, start: 'top bottom', end: 'bottom top', scrub: true } });
}

// La tinta sube y tapa la parte clara
function wipe(gsap, reduce) {
  document.querySelectorAll('[data-wipe]').forEach((w) => {
    const i = w.querySelector('i');
    if (reduce) { gsap.set(i, { yPercent: 0, y: 0, scale: 1 }); return; }
    gsap.fromTo(i, { y: () => w.offsetHeight, scale: 0.25 }, {
      y: 0, scale: 1, ease: 'none',
      scrollTrigger: { trigger: w, start: 'top bottom', end: 'bottom 40%', scrub: 0.3, invalidateOnRefresh: true },
    });
  });
}

// Recorrido fijado: un paso cada vez
function processPin(gsap, ScrollTrigger, reduce) {
  const root = document.querySelector('[data-process]');
  if (!root) return;
  const steps = [...root.querySelectorAll('[data-step]')];
  const imgs = [...root.querySelectorAll('[data-step-img]')];
  const now = root.querySelector('[data-step-now]');
  const set = (n) => {
    steps.forEach((s, i) => s.classList.toggle('on', i === n));
    imgs.forEach((s, i) => s.classList.toggle('on', i <= n));
    if (now) now.textContent = String(n + 1).padStart(2, '0');
  };
  const mm = gsap.matchMedia();
  mm.add('(min-width: 960px)', () => {
    let cur = 0;
    const st = ScrollTrigger.create({
      trigger: root, pin: root.querySelector('[data-process-pin]'), start: 'top top',
      end: () => '+=' + window.innerHeight * 1.2,
      onUpdate: (s) => { const n = Math.min(steps.length - 1, Math.floor(s.progress * steps.length * 0.999)); if (n !== cur) { cur = n; set(n); } },
    });
    return () => st.kill();
  });
}

// Abanico de cartas
function fan(gsap, reduce) {
  const root = document.querySelector('[data-fan]');
  if (!root) return;
  const stage = root.querySelector('[data-fan-stage]');
  const cards = [...root.querySelectorAll('[data-fan-card]')];
  const backs = JSON.parse(root.querySelector('[data-fan-data]').textContent);
  const backEl = root.querySelector('[data-fan-back]');
  const nowEl = root.querySelector('[data-fan-now]');
  const n = cards.length;
  let cur = 0;
  const pose = (d) => {
    const a = Math.abs(d), s = Math.sign(d);
    if (a === 0) return { x: 0, xPercent: 0, rotation: 0, scale: 1, opacity: 1, zIndex: 50 };
    if (a === 1) return { x: 0, xPercent: s * 32, rotation: s * 8, scale: 0.9, opacity: 1, zIndex: 40 };
    if (a === 2) return { x: 0, xPercent: s * 58, rotation: s * 14, scale: 0.8, opacity: 0.85, zIndex: 30 };
    return { x: 0, xPercent: s * 70, rotation: s * 18, scale: 0.7, opacity: 0, zIndex: 10 };
  };
  const render = (instant) => {
    cards.forEach((c, i) => {
      let d = i - cur;
      if (d > n / 2) d -= n; if (d < -n / 2) d += n;
      const p = pose(d);
      c.setAttribute('aria-hidden', String(d !== 0));
      c.style.zIndex = p.zIndex;
      gsap.to(c, { ...p, zIndex: undefined, duration: instant || reduce ? 0 : 0.9, ease: 'expo.out', overwrite: true });
    });
    nowEl.textContent = cur + 1;
    backEl.textContent = backs[cur];
    if (!instant && !reduce) gsap.fromTo(backEl, { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: 0.6, ease: 'expo.out' });
  };
  const go = (k) => { cur = (k + n) % n; render(); };
  root.querySelector('[data-fan-prev]').addEventListener('click', () => go(cur - 1));
  root.querySelector('[data-fan-next]').addEventListener('click', () => go(cur + 1));
  cards.forEach((c, i) => c.addEventListener('click', () => { if (!dragMoved && i !== cur) go(i); }));
  root.tabIndex = 0;
  root.addEventListener('keydown', (e) => { if (e.key === 'ArrowLeft') go(cur - 1); if (e.key === 'ArrowRight') go(cur + 1); });
  let x0 = null, dragMoved = false;
  stage.addEventListener('pointerdown', (e) => { x0 = e.clientX; dragMoved = false; });
  window.addEventListener('pointermove', (e) => {
    if (x0 === null) return;
    const dx = e.clientX - x0;
    if (Math.abs(dx) > 6) dragMoved = true;
    gsap.set(cards[cur], { x: dx * 0.6, rotation: dx * 0.03 });
  });
  window.addEventListener('pointerup', (e) => {
    if (x0 === null) return;
    const dx = e.clientX - x0; x0 = null;
    if (dx < -60) go(cur + 1); else if (dx > 60) go(cur - 1); else render();
  });
  render(true);
}

// Cinta infinita que se puede arrastrar
function marquee(gsap, reduce) {
  document.querySelectorAll('[data-marquee]').forEach((root) => {
    const track = root.querySelector('[data-marquee-track]');
    const half = () => track.scrollWidth / 2;
    let x = 0, v = -0.6, drag = null, last = 0, visible = false;
    if (reduce) return;
    new IntersectionObserver(([e]) => (visible = e.isIntersecting)).observe(root);
    root.addEventListener('pointerdown', (e) => { drag = e.clientX; last = e.clientX; root.setPointerCapture(e.pointerId); });
    root.addEventListener('pointermove', (e) => { if (drag === null) return; const dx = e.clientX - last; last = e.clientX; x += dx; v = dx; });
    const end = () => { drag = null; if (Math.abs(v) < 0.6) v = v < 0 ? -0.6 : 0.6; };
    root.addEventListener('pointerup', end); root.addEventListener('pointercancel', end);
    gsap.ticker.add(() => {
      if (!visible) return;
      if (drag === null) { x += v; v += ((v < 0 ? -0.6 : 0.6) - v) * 0.04; }
      const h = half();
      if (x <= -h) x += h; if (x > 0) x -= h;
      track.style.transform = `translate3d(${x}px,0,0)`;
    });
  });
}

// Lista «Explora»: una foto sigue al ratón
function explore(gsap, fine, reduce) {
  const list = document.querySelector('[data-xlist]');
  const fl = document.querySelector('[data-xfloat]');
  if (!list || !fl || !fine) return;
  const img = fl.querySelector('img');
  const xTo = gsap.quickTo(fl, 'x', { duration: reduce ? 0 : 0.6, ease: 'power3' });
  const yTo = gsap.quickTo(fl, 'y', { duration: reduce ? 0 : 0.6, ease: 'power3' });
  list.querySelectorAll('a').forEach((a) => {
    a.addEventListener('pointerenter', () => { img.src = a.dataset.ximg; fl.classList.add('on'); });
    a.addEventListener('pointerleave', () => fl.classList.remove('on'));
  });
  list.addEventListener('pointermove', (e) => { xTo(e.clientX + 30); yTo(e.clientY - 190); });
  const off = () => fl.classList.remove('on');
  list.addEventListener('pointerleave', off);
  list.addEventListener('click', off);
  window.addEventListener('scroll', off, { passive: true });
  window.addEventListener('pagehide', off);
}

// Orbe de cierre: sube con el scroll
function orb(gsap, reduce) {
  document.querySelectorAll('[data-orb]').forEach((o) => {
    if (reduce) return;
    gsap.fromTo(o, { yPercent: 30, scale: 0.8 }, {
      yPercent: -8, scale: 1, ease: 'none',
      scrollTrigger: { trigger: o.closest('[data-orb-scope]'), start: 'top bottom', end: 'bottom bottom', scrub: 0.4 },
    });
  });
}
