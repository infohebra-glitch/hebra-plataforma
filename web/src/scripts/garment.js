// Escena 3D de la portada: una camisa con su etiqueta colgante de Hebra.
// Geometría procedural (sin modelos externos). El scroll mueve la cámara de la prenda a la etiqueta.
import * as THREE from 'three';

const GRANA = 0x8c304b;

function knitTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const g = c.getContext('2d');
  g.fillStyle = '#808080';
  g.fillRect(0, 0, 256, 256);
  // punto de tejido: columnas de "v" muy finas
  for (let y = 0; y < 256; y += 8) {
    for (let x = 0; x < 256; x += 8) {
      const v = 120 + Math.random() * 30;
      g.fillStyle = `rgb(${v},${v},${v})`;
      g.beginPath();
      g.ellipse(x + 2, y + 4, 2.2, 3.6, 0.5, 0, Math.PI * 2);
      g.ellipse(x + 6, y + 4, 2.2, 3.6, -0.5, 0, Math.PI * 2);
      g.fill();
    }
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(5, 5);
  return t;
}

function tagTexture(logo) {
  const c = document.createElement('canvas');
  c.width = 512; c.height = 800;
  const g = c.getContext('2d');
  g.fillStyle = '#FBFBFA';
  g.fillRect(0, 0, 512, 800);
  // agujero
  g.fillStyle = '#d9d6d5';
  g.beginPath(); g.arc(256, 70, 22, 0, Math.PI * 2); g.fill();
  if (logo) {
    const h = 210, w = (logo.width / logo.height) * h;
    g.drawImage(logo, 256 - w / 2, 150, w, h);
  }
  g.fillStyle = '#14457D';
  g.font = '400 64px "Fraunces Variable", Georgia, serif';
  g.textAlign = 'center';
  g.fillText('Hebra', 256, 450);
  // ondas NFC
  g.strokeStyle = '#8C304B';
  g.lineWidth = 7; g.lineCap = 'round';
  [40, 70, 100].forEach((r) => { g.beginPath(); g.arc(196, 600, r, -0.75, 0.75); g.stroke(); });
  g.fillStyle = '#4A5668';
  g.font = '500 30px "Hanken Grotesk Variable", system-ui, sans-serif';
  g.textAlign = 'left';
  g.fillText('Toca', 300, 590);
  g.fillText('con el móvil', 300, 630);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

function shirtShape() {
  const s = new THREE.Shape();
  // contorno de una camisa de manga corta, de la sisa izquierda en sentido horario
  s.moveTo(-0.44, 1.62);
  s.quadraticCurveTo(0, 1.28, 0.44, 1.62);          // escote
  s.lineTo(1.08, 1.5);                               // hombro
  s.quadraticCurveTo(1.55, 1.32, 1.92, 0.9);         // manga arriba
  s.lineTo(1.6, 0.5);                                // puño
  s.quadraticCurveTo(1.3, 0.72, 1.08, 0.78);         // bajo manga
  s.quadraticCurveTo(1.04, -0.4, 1.12, -1.66);       // costado
  s.quadraticCurveTo(0, -1.74, -1.12, -1.66);        // bajo
  s.quadraticCurveTo(-1.04, -0.4, -1.08, 0.78);
  s.quadraticCurveTo(-1.3, 0.72, -1.6, 0.5);
  s.lineTo(-1.92, 0.9);
  s.quadraticCurveTo(-1.55, 1.32, -1.08, 1.5);
  s.lineTo(-0.44, 1.62);
  return s;
}

function noise(x, y) {
  return Math.sin(x * 2.1 + y * 0.7) * 0.5 + Math.sin(x * 0.9 - y * 1.7 + 1.3) * 0.35 + Math.sin(y * 3.3 + 0.4) * 0.15;
}

// Silueta → máscara en canvas → altura suave (campo difuminado) → plano denso desplazado
function buildShirt(knit) {
  const pts = shirtShape().getPoints(40);
  const minX = -2.05, maxX = 2.05, minY = -1.85, maxY = 1.8;
  const W = maxX - minX, H = maxY - minY;
  const R = 1024, RH = Math.round(R * H / W);
  const toPx = (x, y) => [((x - minX) / W) * R, ((maxY - y) / H) * RH];
  const mask = document.createElement('canvas'); mask.width = R; mask.height = RH;
  const mg = mask.getContext('2d');
  mg.fillStyle = '#000'; mg.fillRect(0, 0, R, RH);
  mg.fillStyle = '#fff'; mg.beginPath();
  pts.forEach((p, i) => { const [px, py] = toPx(p.x, p.y); i ? mg.lineTo(px, py) : mg.moveTo(px, py); });
  mg.closePath(); mg.fill();
  // campo de altura: el blanco "erosionado" por difuminado
  const blur = document.createElement('canvas'); blur.width = R; blur.height = RH;
  const bg = blur.getContext('2d');
  bg.filter = 'blur(52px)'; bg.drawImage(mask, 0, 0);
  const blurData = bg.getImageData(0, 0, R, RH).data;
  const sample = (data, x, y) => {
    let [px, py] = toPx(x, y);
    px = Math.max(0, Math.min(R - 1.001, px)); py = Math.max(0, Math.min(RH - 1.001, py));
    const x0 = Math.floor(px), y0 = Math.floor(py), fx = px - x0, fy = py - y0;
    const v = (ix, iy) => data[(iy * R + ix) * 4] / 255;
    return (v(x0, y0) * (1 - fx) + v(x0 + 1, y0) * fx) * (1 - fy) + (v(x0, y0 + 1) * (1 - fx) + v(x0 + 1, y0 + 1) * fx) * fy;
  };
  const heightAt = (x, y) => {
    const b = Math.max(0, (sample(blurData, x, y) - 0.5) / 0.5);
    const puff = Math.pow(b, 0.75) * 0.22;
    const folds = (noise(x * 1.3, y * 1.1) * 0.035 + Math.sin(y * 5 + x * 0.6) * 0.008) * b;
    return puff + folds;
  };
  const maskTex = new THREE.CanvasTexture(mask);
  const material = new THREE.MeshPhysicalMaterial({
    color: 0xf4f2ef, roughness: 0.95, sheen: 1, sheenRoughness: 0.5, sheenColor: new THREE.Color(0xffffff),
    bumpMap: knit, bumpScale: 0.35, alphaMap: maskTex, alphaTest: 0.5, alphaToCoverage: true, side: THREE.FrontSide,
  });
  const meshes = [1, -1].map((sgn) => {
    const g = new THREE.PlaneGeometry(W, H, 220, Math.round(220 * H / W));
    g.translate(minX + W / 2, minY + H / 2, 0);
    const p = g.attributes.position;
    for (let i = 0; i < p.count; i++) {
      const x = p.getX(i), y = p.getY(i);
      p.setZ(i, heightAt(x, y) * (sgn < 0 ? 0.7 : 1));
    }
    g.computeVertexNormals();
    const m = new THREE.Mesh(g, material);
    m.scale.z = sgn; // la espalda: la misma superficie reflejada, con las caras hacia atrás
    m.castShadow = true; m.receiveShadow = true;
    return m;
  });
  return { meshes, material, heightAt };
}

export function mountGarment(canvas, { reduce, product } = {}) {
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: false });
  } catch (e) {
    canvas.dataset.failed = '';
    return null;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);

  // Luces: luz de estudio suave, con contraluz frío
  scene.add(new THREE.HemisphereLight(0xffffff, 0x0d2a4f, 1.1));
  const key = new THREE.DirectionalLight(0xffffff, 2.4);
  key.position.set(3, 4, 5);
  key.castShadow = true;
  key.shadow.mapSize.set(1024, 1024);
  key.shadow.radius = 6;
  scene.add(key);
  const rim = new THREE.DirectionalLight(0xbcd2ff, 1.6);
  rim.position.set(-4, 2, -3);
  scene.add(rim);

  const root = new THREE.Group();
  scene.add(root);

  // Camisa: silueta inflada como un cojín (plano denso + máscara), así el tejido se ve suave
  const knit = knitTexture();
  const cloth = buildShirt(knit);
  cloth.meshes.forEach((m) => root.add(m));
  const hAt = cloth.heightAt;

  // Cuello: un ribete que sigue el escote
  const collarPts = [];
  for (let i = 0; i <= 24; i++) {
    const u = i / 24, x = -0.46 + u * 0.92;
    const y = 1.6 - Math.sin(u * Math.PI) * 0.31;
    collarPts.push(new THREE.Vector3(x, y, hAt(x, y - 0.05) + 0.02));
  }
  const collar = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(collarPts), 60, 0.035, 10), cloth.material);
  collar.castShadow = true;
  root.add(collar);

  // Tapeta y botones: detalle que da escala y lee "camisa"
  const placketPts = [];
  for (let i = 0; i <= 30; i++) { const y = 1.28 - i * (2.85 / 30); placketPts.push(new THREE.Vector3(0.0, y, hAt(0, y) + 0.004)); }
  const placket = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(placketPts), 60, 0.006, 6), new THREE.MeshStandardMaterial({ color: 0xd9d4cf, roughness: 1 }));
  root.add(placket);
  const btnMat = new THREE.MeshPhysicalMaterial({ color: 0xf2eee8, roughness: 0.25, clearcoat: 1, clearcoatRoughness: 0.2 });
  for (let i = 0; i < 5; i++) {
    const y = 1.12 - i * 0.6;
    const bt = new THREE.Mesh(new THREE.CylinderGeometry(0.042, 0.042, 0.018, 24), btnMat);
    bt.rotation.x = Math.PI / 2;
    bt.position.set(0.06, y, hAt(0.06, y) + 0.012);
    bt.castShadow = true;
    root.add(bt);
  }
  // Bolsillo de pecho
  const pocket = new THREE.Mesh(new THREE.PlaneGeometry(0.42, 0.46, 1, 1), new THREE.MeshStandardMaterial({ color: 0xebe7e2, roughness: 1, transparent: true, opacity: 0.0 }));
  pocket.visible = false;

  // Etiqueta colgante con el hilo grana
  const tagGroup = new THREE.Group();
  tagGroup.position.set(1.0, 0.62, hAt(1.0, 0.62) + 0.03);
  root.add(tagGroup);
  const tagShape = new THREE.Shape();
  const w = 0.26, h = 0.42, r = 0.04;
  tagShape.moveTo(-w + r, -h);
  tagShape.lineTo(w - r, -h); tagShape.quadraticCurveTo(w, -h, w, -h + r);
  tagShape.lineTo(w, h - 0.08); tagShape.lineTo(w - 0.08, h); tagShape.lineTo(-w + 0.08, h); tagShape.lineTo(-w, h - 0.08);
  tagShape.lineTo(-w, -h + r); tagShape.quadraticCurveTo(-w, -h, -w + r, -h);
  const tagGeo = new THREE.ExtrudeGeometry(tagShape, { depth: 0.012, bevelEnabled: false });
  // UV planas para la cara
  const tp = tagGeo.attributes.position, uv = tagGeo.attributes.uv;
  for (let i = 0; i < tp.count; i++) uv.setXY(i, (tp.getX(i) + w) / (2 * w), (tp.getY(i) + h) / (2 * h));
  const tagMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.75 });
  const tag = new THREE.Mesh(tagGeo, tagMat);
  tag.position.y = -h - 0.32;
  tag.castShadow = true;
  const swing = new THREE.Group();
  swing.add(tag);
  tagGroup.add(swing);
  const threadCurve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(-0.02, 0.05, -0.05), new THREE.Vector3(0.04, -0.12, 0.02), new THREE.Vector3(0, -0.32 + 0.37 - 0.36, 0.006),
  ]);
  const thread = new THREE.Mesh(new THREE.TubeGeometry(threadCurve, 20, 0.008, 8), new THREE.MeshStandardMaterial({ color: GRANA, roughness: 0.6 }));
  swing.add(thread);

  const logo = new Image();
  logo.onload = () => { tagMat.map = tagTexture(logo); tagMat.needsUpdate = true; };
  logo.onerror = () => { tagMat.map = tagTexture(null); tagMat.needsUpdate = true; };
  logo.src = canvas.dataset.logo || '/img/logo-blau.png';
  if (document.fonts) document.fonts.ready.then(() => { if (logo.complete) { tagMat.map = tagTexture(logo); tagMat.needsUpdate = true; } });

  // Ondas NFC que salen de la etiqueta
  const rings = [];
  const ringMat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false });
  for (let i = 0; i < 3; i++) {
    const m = new THREE.Mesh(new THREE.RingGeometry(0.3, 0.312, 64), ringMat.clone());
    m.position.set(0, -h - 0.32, 0.02);
    swing.add(m);
    rings.push(m);
  }

  // Sombra suave en el suelo
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(12, 12), new THREE.ShadowMaterial({ opacity: 0.18 }));
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -2.25;
  floor.receiveShadow = true;
  scene.add(floor);

  // Estado controlado desde fuera (scroll) y ratón
  const state = { progress: 0, mx: 0, my: 0 };
  const wide = {
    from: { pos: new THREE.Vector3(-1.5, 0.15, 9.6), look: new THREE.Vector3(-1.7, 0, 0) },
    to: { pos: new THREE.Vector3(1.95, 0.1, 7.0), look: new THREE.Vector3(0.38, -0.3, 0.3) },
  };
  const tall = {
    from: { pos: new THREE.Vector3(0, -1.2, 12.5), look: new THREE.Vector3(0, -1.9, 0) },
    to: { pos: new THREE.Vector3(1.8, -0.5, 7.5), look: new THREE.Vector3(1.5, -0.9, 0.3) },
  };
  const still = { from: { pos: new THREE.Vector3(0.6, 0.1, 10.2), look: new THREE.Vector3(0.15, -0.15, 0) } };
  still.to = still.from;
  let camFrom = wide.from, camTo = wide.to;
  const tmpP = new THREE.Vector3(), tmpL = new THREE.Vector3();

  function resize() {
    const r = canvas.getBoundingClientRect();
    renderer.setSize(r.width, r.height, false);
    camera.aspect = r.width / Math.max(r.height, 1);
    // en vertical, alejar un poco para que quepa
    const portrait = camera.aspect < 0.8;
    camera.fov = portrait ? 40 : 32;
    ({ from: camFrom, to: camTo } = product ? still : portrait ? tall : wide);
    camera.updateProjectionMatrix();
  }
  resize();
  window.addEventListener('resize', resize);
  window.addEventListener('pointermove', (e) => {
    state.mx = (e.clientX / window.innerWidth) * 2 - 1;
    state.my = (e.clientY / window.innerHeight) * 2 - 1;
  }, { passive: true });

  const ease = (t) => t * t * (3 - 2 * t);
  let visible = true, t0 = performance.now(), raf;
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible) loop(); }).observe(canvas);

  function frame(now) {
    const t = (now - t0) / 1000;
    const p = state.progress;
    const zoom = ease(Math.min(1, Math.max(0, (p - 0.25) / 0.5)));
    const turn = ease(Math.min(1, p / 0.45));

    root.rotation.y = -0.42 + turn * 0.62 + (reduce ? 0 : Math.sin(t * 0.35) * 0.06) + state.mx * 0.08;
    root.rotation.x = (reduce ? 0 : Math.sin(t * 0.5) * 0.02) + state.my * 0.03;
    root.position.y = reduce ? 0 : Math.sin(t * 0.8) * 0.05;
    swing.rotation.z = reduce ? 0.08 : Math.sin(t * 1.3) * 0.1 + 0.05;
    swing.rotation.y = reduce ? -0.3 : Math.sin(t * 0.9) * 0.25 - 0.35 + zoom * 0.4;

    tmpP.lerpVectors(camFrom.pos, camTo.pos, zoom);
    tmpL.lerpVectors(camFrom.look, camTo.look, zoom);
    camera.position.copy(tmpP);
    camera.lookAt(tmpL);

    const pulse = Math.min(1, Math.max(0, (p - 0.45) / 0.2));
    rings.forEach((m, i) => {
      const k = ((t * 0.6 + i / 3) % 1);
      m.scale.setScalar(0.6 + k * 1.6);
      m.material.opacity = pulse * (1 - k) * 0.85;
    });
    renderer.render(scene, camera);
  }
  function loop() {
    cancelAnimationFrame(raf);
    const tick = (now) => { frame(now); if (visible) raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
  }
  loop();

  return {
    set progress(v) { state.progress = v; },
    destroy() { cancelAnimationFrame(raf); renderer.dispose(); },
  };
}
