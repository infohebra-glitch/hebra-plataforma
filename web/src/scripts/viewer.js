// Visor 3D interactivo: tres prendas reales (camiseta, blusa, americana) con la etiqueta de Hebra.
// Se gira arrastrando (con inercia), se cambia de prenda con las píldoras y, al tocar la etiqueta, salen las ondas.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const GARMENTS = {
  samarreta: { file: 'samarreta', normal: 'samarreta-normal.jpg', color: '#F3F1EE', roughness: 0.92, clamp: Infinity },
  blusa: { file: 'blusa', normal: null, color: '#ECE9E7', roughness: 0.7, clamp: 1.05 },
  americana: { file: 'americana', normal: 'americana-normal.jpg', color: 'deep', roughness: 0.82, clamp: Infinity },
};

function tagTexture(logo, deep, label) {
  const c = document.createElement('canvas');
  c.width = 512; c.height = 800;
  const g = c.getContext('2d');
  g.fillStyle = '#FBFBFA';
  g.fillRect(0, 0, 512, 800);
  g.fillStyle = '#d9d6d5';
  g.beginPath(); g.arc(256, 70, 22, 0, Math.PI * 2); g.fill();
  if (logo) {
    const h = 230, w = (logo.width / logo.height) * h;
    g.drawImage(logo, 256 - w / 2, 150, w, h);
  }
  g.fillStyle = deep;
  g.font = '600 66px "Hanken Grotesk Variable", system-ui, sans-serif';
  g.textAlign = 'center';
  g.fillText('Hebra', 256, 480);
  g.strokeStyle = deep;
  g.lineWidth = 7; g.lineCap = 'round';
  [34, 60, 86].forEach((r) => { g.beginPath(); g.arc(190, 640, r, -0.75, 0.75); g.stroke(); });
  g.fillStyle = '#5A6270';
  g.font = '500 30px "Hanken Grotesk Variable", system-ui, sans-serif';
  g.textAlign = 'left';
  const [a, b] = label;
  g.fillText(a, 290, 630);
  g.fillText(b, 290, 670);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

export function mountViewer(root, { reduce, onTap } = {}) {
  const canvas = root.querySelector('canvas');
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  } catch (e) {
    root.dataset.failed = '';
    return null;
  }
  const deep = css('--deep') || '#14457D';
  const tint = css('--tint') || '#8FB3E0';
  const lang = document.documentElement.lang;
  const tapLabel = { es: ['Tócala', 'con el móvil'], ca: ['Toca-la', 'amb el mòbil'], en: ['Tap it', 'with your phone'] }[lang] || ['Tócala', 'con el móvil'];

  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.08;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
  camera.position.set(0, 0.1, 11);

  scene.add(new THREE.HemisphereLight(0xffffff, new THREE.Color(deep), 1.25));
  const key = new THREE.DirectionalLight(0xffffff, 2.6);
  key.position.set(3, 4, 6);
  scene.add(key);
  const rim = new THREE.DirectionalLight(new THREE.Color(tint), 2.4);
  rim.position.set(-5, 2, -4);
  scene.add(rim);
  const fill = new THREE.DirectionalLight(0xffffff, 0.5);
  fill.position.set(-2, -3, 4);
  scene.add(fill);

  // giro: lo controla el arrastre; flotación: el tiempo
  const spin = new THREE.Group();
  scene.add(spin);
  const holder = new THREE.Group();
  spin.add(holder);

  // Etiqueta colgante con su hilo
  const tagGroup = new THREE.Group();
  const swing = new THREE.Group();
  tagGroup.add(swing);
  const w = 0.24, h = 0.38, r = 0.035;
  const shape = new THREE.Shape();
  shape.moveTo(-w + r, -h);
  shape.lineTo(w - r, -h); shape.quadraticCurveTo(w, -h, w, -h + r);
  shape.lineTo(w, h - 0.08); shape.lineTo(w - 0.08, h); shape.lineTo(-w + 0.08, h); shape.lineTo(-w, h - 0.08);
  shape.lineTo(-w, -h + r); shape.quadraticCurveTo(-w, -h, -w + r, -h);
  const tagGeo = new THREE.ExtrudeGeometry(shape, { depth: 0.012, bevelEnabled: false });
  const tp = tagGeo.attributes.position, uv = tagGeo.attributes.uv;
  for (let i = 0; i < tp.count; i++) uv.setXY(i, (tp.getX(i) + w) / (2 * w), (tp.getY(i) + h) / (2 * h));
  const tagMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.7 });
  const tag = new THREE.Mesh(tagGeo, tagMat);
  const drop = 0.34;
  tag.position.y = -h - drop;
  swing.add(tag);
  const threadCurve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(0, 0.02, 0), new THREE.Vector3(0.03, -0.14, 0.02), new THREE.Vector3(0, -drop + 0.06, 0.006),
  ]);
  swing.add(new THREE.Mesh(new THREE.TubeGeometry(threadCurve, 20, 0.008, 8), new THREE.MeshStandardMaterial({ color: new THREE.Color(deep), roughness: 0.6 })));
  // zona de toque más generosa que la etiqueta
  const hit = new THREE.Mesh(new THREE.PlaneGeometry(w * 3.2, h * 3), new THREE.MeshBasicMaterial({ visible: false }));
  hit.position.y = -h - drop;
  swing.add(hit);

  const logo = new Image();
  const paintTag = (img) => { tagMat.map = tagTexture(img, deep, tapLabel); tagMat.needsUpdate = true; };
  logo.onload = () => paintTag(logo);
  logo.onerror = () => paintTag(null);
  logo.src = root.dataset.logo || '/img/logo-blau.png';
  document.fonts?.ready.then(() => logo.complete && paintTag(logo.naturalWidth ? logo : null));

  // Ondas al tocar
  const rings = [];
  for (let i = 0; i < 4; i++) {
    const m = new THREE.Mesh(new THREE.RingGeometry(0.3, 0.315, 72), new THREE.MeshBasicMaterial({ color: new THREE.Color(tint), transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false }));
    m.position.set(0, -h - drop, 0.03);
    swing.add(m);
    rings.push(m);
  }
  let pulseAt = -10;

  // Carga de prendas
  const base = root.dataset.model || '/3d/';
  const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
  const texLoader = new THREE.TextureLoader();
  const cache = {};
  let current = null, currentKey = null, fadeIn = 0;

  function prepare(key) {
    if (cache[key]) return cache[key];
    const g = GARMENTS[key];
    cache[key] = new Promise((resolve, reject) => {
      const mat = new THREE.MeshPhysicalMaterial({
        color: g.color === 'deep' ? new THREE.Color(deep).lerp(new THREE.Color('#0b0b10'), 0.45) : new THREE.Color(g.color), roughness: g.roughness,
        sheen: 1, sheenColor: new THREE.Color(g.color === 'deep' ? deep : '#ffffff'), sheenRoughness: g.color === 'deep' ? 0.7 : 0.45,
        side: THREE.DoubleSide,
      });
      if (g.normal) texLoader.load(base + g.normal, (t) => { t.flipY = false; t.anisotropy = 8; mat.normalMap = t; mat.normalScale.set(0.8, 0.8); mat.needsUpdate = true; });
      loader.load(base + g.file + '.glb', (gltf) => {
        const model = gltf.scene;
        model.traverse((o) => { if (o.isMesh) o.material = mat; });
        const box = new THREE.Box3().setFromObject(model);
        const size = box.getSize(new THREE.Vector3()), ctr = box.getCenter(new THREE.Vector3());
        const k = 3.3 / size.y;
        model.scale.setScalar(k);
        model.position.copy(ctr).multiplyScalar(-k);
        const pivot = new THREE.Group();
        pivot.add(model);
        pivot.updateMatrixWorld(true);
        // punto de la etiqueta: bajo delantero, en el lado derecho de la prenda
        const v = new THREE.Vector3(); const pts = [];
        let minY = Infinity, maxX = -Infinity, maxZ = -Infinity;
        model.traverse((o) => {
          if (!o.isMesh) return;
          const pa = o.geometry.attributes.position;
          for (let i = 0; i < pa.count; i += 2) {
            v.fromBufferAttribute(pa, i).applyMatrix4(o.matrixWorld); pts.push(v.clone());
            minY = Math.min(minY, v.y); maxX = Math.max(maxX, v.x); maxZ = Math.max(maxZ, v.z);
          }
        });
        const band = pts.filter((q) => q.y < minY + 0.25 && q.x > maxX * 0.28 && q.x < maxX * 0.62);
        let at = band[0] || new THREE.Vector3(0.5, minY, 0.3);
        band.forEach((q) => { if (q.z > at.z) at = q; });
        resolve({ pivot, at: at.clone().add(new THREE.Vector3(0, 0.04, 0.02)), clamp: g.clamp, mat });
      }, undefined, reject);
    });
    return cache[key];
  }

  async function show(key) {
    if (key === currentKey) return;
    currentKey = key;
    root.dataset.loading = '';
    let item;
    try { item = await prepare(key); } catch (e) { delete root.dataset.loading; return; }
    if (key !== currentKey) return;
    delete root.dataset.loading;
    if (current) holder.remove(current.pivot);
    current = item;
    holder.add(item.pivot);
    item.pivot.add(tagGroup);
    tagGroup.position.copy(item.at);
    fadeIn = 0;
    rot.v += reduce ? 0 : 0.18; // pequeño giro de entrada
    if (!reduce) pulseAt = clock - 0.4;
  }

  // Arrastre con inercia
  const rot = { y: -0.35, v: 0, x: 0 };
  let dragging = false, lastX = 0, lastY = 0, moved = 0, downAt = 0;
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
  function hitTag(e) {
    const rc = canvas.getBoundingClientRect();
    ndc.set(((e.clientX - rc.left) / rc.width) * 2 - 1, -((e.clientY - rc.top) / rc.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    return ray.intersectObjects([hit, tag], false).length > 0;
  }
  canvas.addEventListener('pointerdown', (e) => {
    dragging = true; moved = 0; downAt = performance.now();
    lastX = e.clientX; lastY = e.clientY;
    canvas.setPointerCapture(e.pointerId);
    root.classList.add('grab');
  });
  canvas.addEventListener('pointermove', (e) => {
    if (!dragging) { canvas.style.cursor = hitTag(e) ? 'pointer' : ''; return; }
    const dx = e.clientX - lastX, dy = e.clientY - lastY;
    lastX = e.clientX; lastY = e.clientY;
    moved += Math.abs(dx) + Math.abs(dy);
    rot.v = dx * 0.0085;
    rot.y += rot.v;
    rot.x = Math.max(-0.35, Math.min(0.35, rot.x + dy * 0.003));
  });
  const up = (e) => {
    if (!dragging) return;
    dragging = false;
    root.classList.remove('grab');
    if (moved < 6 && performance.now() - downAt < 400 && hitTag(e)) tap();
  };
  canvas.addEventListener('pointerup', up);
  canvas.addEventListener('pointercancel', up);
  // en móvil, deja hacer scroll vertical: solo capturamos el gesto horizontal
  canvas.style.touchAction = 'pan-y';

  function tap() {
    pulseAt = clock;
    onTap?.();
  }

  // Tamaño
  function resize() {
    const rc = root.getBoundingClientRect();
    renderer.setSize(rc.width, rc.height, false);
    camera.aspect = rc.width / Math.max(rc.height, 1);
    camera.fov = camera.aspect < 0.75 ? 38 : 30;
    camera.updateProjectionMatrix();
  }
  resize();
  new ResizeObserver(resize).observe(root);

  // Bucle
  let visible = true, raf, clock = 0, prev = performance.now();
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible) loop(); }).observe(root);
  const ext = { mx: 0, my: 0, scroll: 0 };
  window.addEventListener('pointermove', (e) => {
    ext.mx = (e.clientX / window.innerWidth) * 2 - 1;
    ext.my = (e.clientY / window.innerHeight) * 2 - 1;
  }, { passive: true });

  function frame(now) {
    const dt = Math.min(0.05, (now - prev) / 1000); prev = now; clock += dt;
    if (!dragging) {
      rot.v *= Math.pow(0.05, dt); // inercia
      rot.y += rot.v;
      if (!reduce && Math.abs(rot.v) < 0.002) rot.y += dt * 0.12; // giro lento en reposo
      rot.x *= Math.pow(0.2, dt);
    }
    const lim = current ? current.clamp : Infinity;
    if (Number.isFinite(lim)) {
      const c = Math.max(-lim, Math.min(lim, rot.y));
      if (c !== rot.y) { rot.y = c; rot.v *= -0.4; }
    }
    spin.rotation.y = rot.y + ext.mx * 0.06;
    spin.rotation.x = rot.x + ext.my * 0.03;
    spin.position.y = (reduce ? 0 : Math.sin(clock * 0.8) * 0.05) + ext.scroll * 0.6;
    spin.scale.setScalar(1 - ext.scroll * 0.12);
    if (current && fadeIn < 1) {
      fadeIn = Math.min(1, fadeIn + dt * 1.6);
      const e = 1 - Math.pow(1 - fadeIn, 3);
      holder.scale.setScalar(0.92 + e * 0.08);
      holder.position.y = (1 - e) * -0.25;
    }
    swing.rotation.z = reduce ? 0.06 : Math.sin(clock * 1.3) * 0.12 + 0.04 + rot.v * -2;
    swing.rotation.y = reduce ? -0.2 : Math.sin(clock * 0.9) * 0.3 - 0.25;
    const since = clock - pulseAt;
    rings.forEach((m, i) => {
      const k = since * 0.9 - i * 0.18;
      const on = k > 0 && k < 1;
      m.scale.setScalar(0.5 + Math.max(0, k) * 2.6);
      m.material.opacity = on ? (1 - k) * 0.95 : 0;
    });
    camera.position.set(0, 0.05, camera.aspect < 0.75 ? 12.5 : 11.2);
    camera.lookAt(0, -0.4, 0);
    renderer.render(scene, camera);
  }
  function loop() {
    cancelAnimationFrame(raf);
    const tick = (now) => { frame(now); if (visible) raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
  }
  loop();

  return {
    show,
    tap,
    nudge: (d) => { rot.v += d * 0.09; },
    preload: (keys) => keys.forEach((k) => prepare(k).catch(() => {})),
    set scroll(v) { ext.scroll = v; },
  };
}
