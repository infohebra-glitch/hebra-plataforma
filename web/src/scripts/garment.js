// Escena 3D de la portada: una camisa con su etiqueta colgante de Hebra.
// Geometría procedural (sin modelos externos). El scroll mueve la cámara de la prenda a la etiqueta.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';

const GRANA = 0x8c304b;

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

  // Camiseta: modelo 3D real (algodón, punto jersey), comprimido con meshopt
  const cloth = new THREE.MeshPhysicalMaterial({
    color: 0xf4f2ef, roughness: 0.9, sheen: 1, sheenRoughness: 0.5, sheenColor: new THREE.Color(0xffffff),
    side: THREE.DoubleSide, transparent: true, opacity: 0,
  });
  const base = canvas.dataset.model || '/3d/';
  new THREE.TextureLoader().load(base + 'samarreta-normal.jpg', (t) => {
    t.flipY = false; t.anisotropy = 8; cloth.normalMap = t; cloth.normalScale.set(0.8, 0.8); cloth.needsUpdate = true;
  });
  const shirtHolder = new THREE.Group();
  root.add(shirtHolder);
  let shownAt = 0;
  const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
  loader.load(base + 'samarreta.glb', (gltf) => {
    const model = gltf.scene;
    model.traverse((o) => { if (o.isMesh) { o.material = cloth; o.castShadow = true; o.receiveShadow = true; } });
    const box = new THREE.Box3().setFromObject(model);
    const size = box.getSize(new THREE.Vector3()), ctr = box.getCenter(new THREE.Vector3());
    const k = 3.4 / size.y;
    model.scale.setScalar(k);
    model.position.copy(ctr).multiplyScalar(-k);
    shirtHolder.add(model);
    model.updateMatrixWorld(true);
    // la etiqueta cuelga del bajo de la manga derecha
    const v = new THREE.Vector3(); let maxX = -Infinity; const pts = [];
    model.traverse((o) => {
      if (!o.isMesh) return;
      const pa = o.geometry.attributes.position;
      for (let i = 0; i < pa.count; i += 3) { v.fromBufferAttribute(pa, i).applyMatrix4(o.matrixWorld); pts.push(v.clone()); if (v.x > maxX) maxX = v.x; }
    });
    const tip = pts.filter((q) => q.x > maxX * 0.86);
    let low = tip[0]; tip.forEach((q) => { if (q.y < low.y) low = q; });
    tagGroup.position.set(low.x - 0.06, low.y + 0.02, low.z + 0.02);
    tagGroup.visible = true;
    // encuadres finales centrados en la etiqueta
    const ty = low.y - 0.74;
    wide.to.look.set(low.x - 0.25, ty, 0.3); wide.to.pos.copy(wide.to.look).add(new THREE.Vector3(1.57, 0.4, 6.7));
    tall.to.look.set(low.x + 0.5, ty - 0.7, 0.3); tall.to.pos.copy(tall.to.look).add(new THREE.Vector3(0.3, 0.4, 7.2));
    shownAt = performance.now();
  });

  // Etiqueta colgante con el hilo grana
  const tagGroup = new THREE.Group();
  tagGroup.visible = false;
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
    if (shownAt && cloth.opacity < 1) {
      cloth.opacity = Math.min(1, (now - shownAt) / 900);
      if (cloth.opacity >= 1) { cloth.transparent = false; cloth.needsUpdate = true; }
    }
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
