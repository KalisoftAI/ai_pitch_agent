const SANS = '"Segoe UI", "Helvetica Neue", Arial, sans-serif';
const DISPLAY = '"Arial Black", "Segoe UI", Arial, sans-serif';
const SERIF = 'Georgia, "Times New Roman", serif';
const MONO = '"Cascadia Mono", Consolas, "Courier New", monospace';

const canvas = document.getElementById("stage");
const ctx = canvas.getContext("2d", { alpha: true });
const threeCanvas = document.getElementById("three");
const off = document.createElement("canvas");
const octx = off.getContext("2d", { alpha: false });

let DATA = null;
let W = 1280;
let H = 720;
let U = 1;
let M = 56;
let images = new Map();
let THREE = null;
let three = null;
let threeSceneIndex = -1;
let noiseTile = null;
let activeThree = false;

const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, t) => a + (b - a) * t;
const seg = (t, a, b) => clamp((t - a) / Math.max(0.0001, b - a));
const ss = (t) => {
  t = clamp(t);
  return t * t * (3 - 2 * t);
};
const eo = (t) => 1 - Math.pow(1 - clamp(t), 3);
const ei = (t) => Math.pow(clamp(t), 3);
const eio = (t) => {
  t = clamp(t);
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
};
const spring = (t, k = 7, z = 0.42) => {
  t = Math.max(0, t);
  return 1 - Math.exp(-z * k * t) * Math.cos(k * Math.sqrt(1 - z * z) * t * 1.6);
};
const mulberry = (seed) => {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
};

function alpha(color, a) {
  if (!color) return `rgba(255,255,255,${a})`;
  const value = String(color).trim();
  if (value.startsWith("#")) {
    let hex = value.slice(1);
    if (hex.length === 3) hex = hex.split("").map((c) => c + c).join("");
    const n = Number.parseInt(hex, 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
  }
  return value;
}

function mix(a, b, t) {
  const pa = parseHex(a);
  const pb = parseHex(b);
  const p = (i) => Math.round(lerp(pa[i], pb[i], t));
  return `rgb(${p(0)},${p(1)},${p(2)})`;
}

function parseHex(value) {
  let hex = String(value || "#000000").replace("#", "");
  if (hex.length === 3) hex = hex.split("").map((c) => c + c).join("");
  const n = Number.parseInt(hex, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function roundRect(c, x, y, w, h, r) {
  const radius = Math.min(r, Math.abs(w) / 2, Math.abs(h) / 2);
  c.beginPath();
  c.moveTo(x + radius, y);
  c.arcTo(x + w, y, x + w, y + h, radius);
  c.arcTo(x + w, y + h, x, y + h, radius);
  c.arcTo(x, y + h, x, y, radius);
  c.arcTo(x, y, x + w, y, radius);
  c.closePath();
}

function font(size, weight = 400, family = SANS) {
  return `${weight} ${Math.max(1, Math.round(size))}px ${family}`;
}

function measure(c, text, f) {
  c.font = f;
  return c.measureText(text).width;
}

function wrap(c, text, maxWidth, f) {
  c.font = f;
  const words = String(text || "").replace(/\s+/g, " ").trim().split(" ").filter(Boolean);
  const lines = [];
  let line = "";
  for (const word of words) {
    const test = line ? `${line} ${word}` : word;
    if (c.measureText(test).width <= maxWidth || !line) {
      line = test;
      continue;
    }
    lines.push(line);
    line = word;
    if (c.measureText(line).width > maxWidth) {
      let chunk = "";
      for (const char of line) {
        if (c.measureText(chunk + char).width > maxWidth && chunk) {
          lines.push(chunk);
          chunk = char;
        } else {
          chunk += char;
        }
      }
      line = chunk;
    }
  }
  if (line) lines.push(line);
  return lines.length ? lines : [""];
}

function drawTextLines(c, lines, x, y, lineHeight, color, align = "left") {
  c.save();
  c.fillStyle = color;
  c.textAlign = align;
  c.textBaseline = "top";
  lines.forEach((line, index) => c.fillText(line, x, y + index * lineHeight));
  c.restore();
}

function fitTitle(c, text, maxWidth, maxLines, maxSize, minSize, weight = 900) {
  const value = String(text || "").trim();
  let size = maxSize;
  let lines = [];
  for (; size >= minSize; size -= Math.max(1, size * 0.035)) {
    const f = font(size, weight, DISPLAY);
    lines = wrap(c, value, maxWidth, f);
    if (lines.length <= maxLines) break;
  }
  const f = font(size, weight, DISPLAY);
  c.font = f;
  lines = wrap(c, value, maxWidth, f).slice(0, maxLines);
  return { size, lines, font: f, width: Math.max(...lines.map((line) => c.measureText(line).width), 0) };
}

function drawTitle(c, text, x, y, maxWidth, maxLines, maxSize, minSize, color, opts = {}) {
  const { upper = false, align = "left", reveal = 1, weight = 900 } = opts;
  const value = upper ? String(text || "").toUpperCase() : text;
  const fitted = fitTitle(c, value, maxWidth, maxLines, maxSize, minSize, weight);
  const lineHeight = fitted.size * 1.03;
  c.save();
  if (reveal < 1) {
    const clipX = align === "center" ? x - maxWidth / 2 : x;
    c.beginPath();
    c.rect(clipX - 8, y - fitted.size * 0.15, maxWidth * reveal + 16, fitted.lines.length * lineHeight + fitted.size * 0.4);
    c.clip();
  }
  c.globalAlpha *= clamp(reveal * 1.6);
  drawTextLines(c, fitted.lines, x, y, lineHeight, color, align);
  c.restore();
  return y + fitted.lines.length * lineHeight;
}

function drawBody(c, text, x, y, maxWidth, maxLines, size, color, lineHeightFactor = 1.5) {
  const f = font(size, 400, SANS);
  const lines = wrap(c, text, maxWidth, f);
  const shown = lines.slice(0, maxLines);
  if (lines.length > maxLines && shown.length) {
    let last = shown[shown.length - 1];
    while (last.length > 1 && c.measureText(`${last}…`).width > maxWidth) last = last.slice(0, -1);
    shown[shown.length - 1] = `${last.trim()}…`;
  }
  drawTextLines(c, shown, x, y, size * lineHeightFactor, color);
  return y + shown.length * size * lineHeightFactor;
}

function drawKicker(c, text, x, y, color, accent, size = 13) {
  c.save();
  c.fillStyle = accent;
  c.fillRect(x, y + size * 0.38, size * 1.6, Math.max(2, size * 0.16));
  c.font = font(size, 700, MONO);
  c.fillStyle = color;
  c.textBaseline = "middle";
  c.fillText(String(text || "").toUpperCase(), x + size * 2.1, y + size * 0.42);
  c.restore();
}

function drawImageCover(c, image, x, y, w, h, zoom = 1, panX = 0, panY = 0) {
  if (!image) return;
  const iw = image.naturalWidth || image.width;
  const ih = image.naturalHeight || image.height;
  if (!iw || !ih) return;
  const scale = Math.max(w / iw, h / ih) * zoom;
  const dw = iw * scale;
  const dh = ih * scale;
  c.drawImage(image, x + (w - dw) / 2 + panX * w, y + (h - dh) / 2 + panY * h, dw, dh);
}

function drawGrid(c, x, y, w, h, gap, color, offset = 0) {
  c.save();
  c.strokeStyle = color;
  c.lineWidth = Math.max(1, U * 0.9);
  c.beginPath();
  for (let gx = x - gap + (offset % gap); gx < x + w; gx += gap) {
    c.moveTo(gx, y);
    c.lineTo(gx, y + h);
  }
  for (let gy = y - gap + (offset % gap); gy < y + h; gy += gap) {
    c.moveTo(x, gy);
    c.lineTo(x + w, gy);
  }
  c.stroke();
  c.restore();
}

function drawAbstract(c, x, y, w, h, seed, accent, radius = 24) {
  const pal = DATA.palette;
  const rnd = mulberry(seed * 7919 + 13);
  c.save();
  roundRect(c, x, y, w, h, radius);
  c.clip();
  const grad = c.createLinearGradient(x, y, x + w, y + h);
  grad.addColorStop(0, mix(pal.panel, pal.bg, 0.25));
  grad.addColorStop(0.55, mix(pal.panel, accent, 0.18));
  grad.addColorStop(1, mix(pal.bg, accent, 0.32));
  c.fillStyle = grad;
  c.fillRect(x, y, w, h);
  drawGrid(c, x, y, w, h, Math.max(22, 38 * U), alpha(pal.ink, 0.07), 0);

  for (let i = 0; i < 8; i++) {
    const cx = x + w * (0.12 + rnd() * 0.78);
    const cy = y + h * (0.12 + rnd() * 0.76);
    const r = Math.min(w, h) * (0.05 + rnd() * 0.22);
    c.strokeStyle = alpha(i % 2 ? accent : pal.ink, 0.12 + rnd() * 0.16);
    c.lineWidth = Math.max(1, (1 + rnd() * 2.5) * U);
    c.beginPath();
    c.arc(cx, cy, r, rnd() * Math.PI, Math.PI * (1.15 + rnd()));
    c.stroke();
  }

  c.save();
  c.translate(x + w * 0.5, y + h * 0.5);
  c.rotate(-0.18);
  for (let i = 0; i < 5; i++) {
    c.fillStyle = alpha(i % 2 ? accent : pal.ink, 0.05 + i * 0.018);
    c.fillRect(-w * 0.7 + i * w * 0.2, -h * 0.7, w * 0.1, h * 1.4);
  }
  c.restore();

  c.font = font(Math.min(w, h) * 0.42, 900, DISPLAY);
  c.fillStyle = alpha(accent, 0.2);
  c.textBaseline = "bottom";
  c.fillText(String(seed).padStart(2, "0"), x + w * 0.07, y + h * 0.93);
  c.restore();
}

function disposeThreeGroup(group) {
  for (const child of [...group.children]) {
    group.remove(child);
    child.traverse?.((node) => {
      node.geometry?.dispose?.();
      if (Array.isArray(node.material)) node.material.forEach((item) => item.dispose?.());
      else node.material?.dispose?.();
    });
  }
}

async function initThree() {
  if (!threeCanvas || !window.WebGLRenderingContext) return;
  try {
    THREE = await import("three");
  } catch (error) {
    console.warn("[film] Three.js unavailable, using canvas fallback", error);
    return;
  }
  try {
    const renderer = new THREE.WebGLRenderer({
      canvas: threeCanvas,
      alpha: true,
      antialias: true,
      powerPreference: "low-power",
    });
    renderer.setPixelRatio(1);
    renderer.setSize(W, H, false);
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(34, W / H, 0.1, 100);
    const root = new THREE.Group();
    scene.add(root);
    scene.add(new THREE.HemisphereLight(0xf4f7ff, 0x090a12, 1.45));
    const key = new THREE.DirectionalLight(0xffffff, 2.4);
    key.position.set(5, 7, 6);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0xff4d2e, 1.35);
    rim.position.set(-6, 3, -5);
    scene.add(rim);
    const fill = new THREE.PointLight(0x7c5cff, 28, 26, 2);
    fill.position.set(-2, 4, 4);
    scene.add(fill);
    three = { renderer, scene, camera, root, key, rim, fill, bars: [], rings: [], dust: [] };
    threeCanvas.style.width = `${W}px`;
    threeCanvas.style.height = `${H}px`;
  } catch (error) {
    console.warn("[film] WebGL unavailable, using canvas fallback", error);
    three = null;
  }
}

function buildThreeScene(scene) {
  if (!three) return;
  disposeThreeGroup(three.root);
  const pal = DATA.palette;
  const accent = new THREE.Color(scene.accent || pal.signal);
  const panel = new THREE.Color(pal.panel || "#121725");
  const ink = new THREE.Color(pal.ink || "#f5f7ff");
  const chart = Array.isArray(scene.chart) && scene.chart.length ? scene.chart : [0.3, 0.55, 0.4, 0.7, 0.5, 0.82, 0.62, 0.9, 0.74];
  const base = new THREE.MeshStandardMaterial({ color: panel, roughness: 0.62, metalness: 0.18 });
  const hot = new THREE.MeshStandardMaterial({
    color: accent,
    emissive: accent,
    emissiveIntensity: 0.22,
    roughness: 0.36,
    metalness: 0.42,
  });
  const pale = new THREE.MeshStandardMaterial({ color: ink, roughness: 0.8, metalness: 0.05, transparent: true, opacity: 0.22 });
  const slab = new THREE.Mesh(new THREE.CylinderGeometry(5.4, 5.7, 0.32, 8), base);
  slab.position.y = -1.9;
  slab.rotation.y = Math.PI / 8;
  three.root.add(slab);
  const grid = new THREE.GridHelper(13, 26, accent, new THREE.Color(pal.ink || "#ffffff"));
  grid.position.y = -1.72;
  grid.material.transparent = true;
  grid.material.opacity = 0.13;
  three.root.add(grid);
  three.bars = [];
  chart.forEach((value, index) => {
    const height = 0.5 + value * 4.2;
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(0.62, height, 0.62), index === chart.length - 2 ? hot : base);
    mesh.position.set((index - (chart.length - 1) / 2) * 0.82, -1.7 + height / 2, (index % 2 ? -0.5 : 0.5));
    mesh.castShadow = true;
    three.root.add(mesh);
    three.bars.push({ mesh, height, index });
  });
  three.rings = [];
  for (let index = 0; index < 3; index++) {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(2.5 + index * 0.85, 0.018 + index * 0.006, 8, 96),
      index === 1 ? hot : pale,
    );
    ring.rotation.x = Math.PI / 2.35;
    ring.position.y = 1.05 + index * 0.18;
    three.root.add(ring);
    three.rings.push(ring);
  }
  const orb = new THREE.Mesh(new THREE.IcosahedronGeometry(0.48, 1), hot);
  orb.position.set(-3.8, 1.7, -1.6);
  three.root.add(orb);
  three.orb = orb;
  three.dust = [];
  const dustMat = new THREE.PointsMaterial({ color: ink, size: 0.035, transparent: true, opacity: 0.42, depthWrite: false });
  const positions = [];
  for (let index = 0; index < 120; index++) {
    const angle = index * 2.39996;
    const radius = 2.5 + ((index * 37) % 100) / 100 * 5.5;
    positions.push(Math.cos(angle) * radius, -1.4 + ((index * 53) % 100) / 100 * 6.4, Math.sin(angle) * radius);
  }
  const points = new THREE.Points(new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(positions, 3)), dustMat);
  three.root.add(points);
  three.dust = points;
  threeSceneIndex = scene.index;
}

function renderThree(scene, local, p) {
  if (!three) return false;
  if (threeSceneIndex !== scene.index) buildThreeScene(scene);
  const pal = DATA.palette;
  const accent = new THREE.Color(scene.accent || pal.signal);
  const camera = three.camera;
  const cameraName = scene.camera || "orbit";
  const angle = -0.6 + local * 0.16 + p * 0.42;
  const push = clamp(p);
  if (cameraName === "orbit") {
    camera.position.set(Math.sin(angle) * 9.6, 5.1 + Math.sin(angle * 0.8) * 0.5, Math.cos(angle) * 9.6);
  } else if (cameraName === "push-in") {
    camera.position.set(6.8, 4.7, 9.6 - push * 2.6);
  } else if (cameraName === "pull-out") {
    camera.position.set(6.8, 4.7, 7.1 + push * 2.8);
  } else if (cameraName === "pan-left") {
    camera.position.set(8.6 - push * 2.2, 4.6, 8.2);
  } else if (cameraName === "pan-right") {
    camera.position.set(5.2 + push * 2.2, 4.6, 8.2);
  } else if (cameraName === "tilt") {
    camera.position.set(7.2, 5.4 + push * 1.8, 8.8);
  } else {
    camera.position.set(7.4, 5.1, 9.3);
  }
  camera.lookAt(0, 0.15, 0);
  three.root.rotation.y = Math.sin(local * 0.22) * 0.08;
  three.bars.forEach(({ mesh, height, index }) => {
    const grow = eo(seg(local, 0.08 + index * 0.055, 0.58 + index * 0.055));
    mesh.scale.y = Math.max(0.04, grow);
    mesh.position.y = -1.7 + (height * Math.max(0.04, grow)) / 2;
    mesh.material = index === three.bars.length - 2 ? mesh.material : mesh.material;
  });
  three.rings.forEach((ring, index) => {
    ring.rotation.z = local * (0.08 + index * 0.035) * (index % 2 ? -1 : 1);
    ring.material.emissive?.copy(accent);
    ring.material.emissiveIntensity = 0.12 + index * 0.04;
  });
  if (three.orb) {
    three.orb.position.y = 1.7 + Math.sin(local * 1.3) * 0.18;
    three.orb.rotation.x = local * 0.35;
    three.orb.rotation.y = local * 0.52;
  }
  if (three.dust) three.dust.rotation.y = local * 0.035;
  three.rim.color.copy(accent);
  three.fill.color.copy(accent);
  three.renderer.render(three.scene, camera);
  threeCanvas.style.opacity = "1";
  activeThree = true;
  return true;
}

function hideThree() {
  if (!activeThree) return;
  threeCanvas.style.opacity = "0";
  activeThree = false;
}

function ensureNoise() {
  if (noiseTile) return noiseTile;
  noiseTile = document.createElement("canvas");
  noiseTile.width = 180;
  noiseTile.height = 180;
  const c = noiseTile.getContext("2d");
  const image = c.createImageData(noiseTile.width, noiseTile.height);
  const rnd = mulberry(911);
  for (let i = 0; i < image.data.length; i += 4) {
    const value = Math.round(rnd() * 255);
    image.data[i] = value;
    image.data[i + 1] = value;
    image.data[i + 2] = value;
    image.data[i + 3] = 255;
  }
  c.putImageData(image, 0, 0);
  return noiseTile;
}

function applyEffects(c, scene, local, p, w, h, t) {
  const effects = Array.isArray(scene.effects) ? scene.effects : [];
  if (!effects.length) return;
  const pal = DATA.palette;
  const accent = scene.accent || pal.signal;
  c.save();
  if (effects.includes("letterbox")) {
    const bar = h * 0.055;
    c.fillStyle = "#000000";
    c.fillRect(0, 0, w, bar);
    c.fillRect(0, h - bar, w, bar);
  }
  if (effects.includes("grid")) {
    drawGrid(c, 0, 0, w, h, Math.max(38, 62 * U), alpha(pal.ink, 0.05), local * 18 * U);
  }
  if (effects.includes("grain")) {
    const tile = ensureNoise();
    const pattern = c.createPattern(tile, "repeat");
    if (pattern) {
      c.globalAlpha = 0.055;
      c.fillStyle = pattern;
      const offset = Math.floor(t * 17) % 180;
      c.translate(-offset, -offset);
      c.fillRect(0, 0, w + 180, h + 180);
      c.setTransform(1, 0, 0, 1, 0, 0);
    }
  }
  if (effects.includes("vignette")) {
    const grad = c.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.18, w / 2, h / 2, Math.max(w, h) * 0.72);
    grad.addColorStop(0, "rgba(0,0,0,0)");
    grad.addColorStop(0.68, "rgba(0,0,0,0.1)");
    grad.addColorStop(1, "rgba(0,0,0,0.5)");
    c.fillStyle = grad;
    c.fillRect(0, 0, w, h);
  }
  if (effects.includes("scanlines")) {
    c.globalAlpha = 0.11;
    c.fillStyle = "#000000";
    for (let y = 0; y < h; y += Math.max(3, 4 * U)) c.fillRect(0, y, w, Math.max(1, U));
  }
  if (effects.includes("particles")) {
    const rnd = mulberry(scene.index * 177 + 31);
    c.globalAlpha = 0.72;
    for (let i = 0; i < 42; i++) {
      const x = (rnd() * w + local * (8 + rnd() * 18)) % w;
      const y = (rnd() * h - local * (5 + rnd() * 13) + h) % h;
      const r = (0.6 + rnd() * 2.1) * U;
      c.fillStyle = alpha(i % 4 === 0 ? accent : pal.ink, 0.16 + rnd() * 0.34);
      c.beginPath();
      c.arc(x, y, r, 0, Math.PI * 2);
      c.fill();
    }
  }
  if (effects.includes("lightleak")) {
    const x = w * (0.82 + Math.sin(local * 0.4) * 0.1);
    const grad = c.createRadialGradient(x, -h * 0.1, 0, x, -h * 0.1, Math.max(w, h) * 0.8);
    grad.addColorStop(0, alpha(accent, 0.32));
    grad.addColorStop(0.42, alpha(accent, 0.1));
    grad.addColorStop(1, "rgba(0,0,0,0)");
    c.fillStyle = grad;
    c.fillRect(0, 0, w, h);
  }
  if (effects.includes("bokeh")) {
    const rnd = mulberry(scene.index * 91 + 5);
    c.globalAlpha = 0.45;
    for (let i = 0; i < 16; i++) {
      const x = rnd() * w;
      const y = rnd() * h;
      const r = (18 + rnd() * 74) * U;
      const grad = c.createRadialGradient(x, y, 0, x, y, r);
      grad.addColorStop(0, alpha(accent, 0.07 + rnd() * 0.1));
      grad.addColorStop(1, "rgba(0,0,0,0)");
      c.fillStyle = grad;
      c.beginPath();
      c.arc(x, y, r, 0, Math.PI * 2);
      c.fill();
    }
  }
  if (effects.includes("glitch")) {
    const pulse = Math.sin(t * 7.1) * Math.sin(t * 2.3);
    if (pulse > 0.72) {
      const rnd = mulberry(Math.floor(t * 12) * 73 + scene.index);
      c.globalAlpha = 0.5;
      for (let i = 0; i < 7; i++) {
        const y = rnd() * h;
        const height = 2 + rnd() * 16 * U;
        c.fillStyle = i % 2 ? alpha(accent, 0.32) : "rgba(0,255,255,0.16)";
        c.fillRect(0, y, w, height);
      }
    }
  }
  if (effects.includes("chromatic")) {
    c.globalAlpha = 0.18;
    c.strokeStyle = accent;
    c.lineWidth = Math.max(2, 3 * U);
    c.strokeRect(4 * U, 4 * U, w - 8 * U, h - 8 * U);
    c.strokeStyle = "rgba(0,255,255,0.4)";
    c.strokeRect(9 * U, 9 * U, w - 18 * U, h - 18 * U);
  }
  c.restore();
}

function drawCard(c, scene, x, y, w, h, local, p, radius = 22, rotate = 0, lift = 0) {
  const pal = DATA.palette;
  const accent = scene.accent || pal.signal;
  const image = scene.asset ? images.get(scene.asset) : null;
  const zoom = 1.04 + clamp(p) * 0.05 + lift * 0.01;
  c.save();
  c.translate(x + w / 2, y + h / 2);
  c.rotate(rotate);
  c.translate(-w / 2, -h / 2);
  c.shadowColor = "rgba(0,0,0,0.42)";
  c.shadowBlur = 36 * U;
  c.shadowOffsetY = 20 * U;
  roundRect(c, 0, 0, w, h, radius);
  c.fillStyle = pal.panel;
  c.fill();
  c.shadowColor = "transparent";
  roundRect(c, 0, 0, w, h, radius);
  c.clip();
  if (image) {
    drawImageCover(c, image, 0, 0, w, h, zoom, (scene.index % 2 ? 1 : -1) * 0.01 * p, -0.01 * p);
    const grad = c.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, "rgba(0,0,0,0.02)");
    grad.addColorStop(0.65, "rgba(0,0,0,0.18)");
    grad.addColorStop(1, "rgba(0,0,0,0.72)");
    c.fillStyle = grad;
    c.fillRect(0, 0, w, h);
  } else {
    drawAbstract(c, 0, 0, w, h, scene.index + 1, accent, 0);
  }
  c.strokeStyle = alpha(pal.ink, 0.18);
  c.lineWidth = Math.max(1, U);
  roundRect(c, 0.5, 0.5, w - 1, h - 1, radius);
  c.stroke();

  const label = (scene.visual || "Motion study").replace(/\s+/g, " ").trim();
  if (label) {
    const f = font(11 * U, 700, MONO);
    const lines = wrap(c, label, w - 34 * U, f).slice(0, 2);
    const pad = 15 * U;
    const lineH = 15 * U;
    c.fillStyle = "rgba(0,0,0,0.38)";
    roundRect(c, pad, h - pad - lines.length * lineH - 10 * U, w - pad * 2, lines.length * lineH + 10 * U, 8 * U);
    c.fill();
    c.font = f;
    c.fillStyle = alpha("#ffffff", 0.86);
    c.textBaseline = "top";
    lines.forEach((line, i) => c.fillText(line.toUpperCase(), pad + 9 * U, h - pad - lines.length * lineH - 2 * U + i * lineH));
  }
  c.restore();
}

function backdrop(c, scene, local, p, w, h) {
  const pal = DATA.palette;
  const accent = scene.accent || pal.signal;
  const bg = c.createLinearGradient(0, 0, w, h);
  bg.addColorStop(0, pal.bg);
  bg.addColorStop(0.58, mix(pal.bg, pal.panel, 0.55));
  bg.addColorStop(1, mix(pal.bg, accent, 0.2));
  c.fillStyle = bg;
  c.fillRect(0, 0, w, h);

  const glow = c.createRadialGradient(w * (0.2 + (scene.index % 3) * 0.3), h * 0.3, 0, w * 0.5, h * 0.5, Math.max(w, h) * 0.8);
  glow.addColorStop(0, alpha(accent, 0.16));
  glow.addColorStop(0.55, alpha(accent, 0.04));
  glow.addColorStop(1, "rgba(0,0,0,0)");
  c.fillStyle = glow;
  c.fillRect(0, 0, w, h);

  drawGrid(c, 0, 0, w, h, Math.max(44, 74 * U), alpha(pal.ink, 0.045), local * 12 * U);

  c.save();
  c.globalAlpha = 0.055;
  c.font = font(h * 0.72, 900, DISPLAY);
  c.fillStyle = pal.ink;
  c.textAlign = "right";
  c.textBaseline = "middle";
  c.fillText(String(scene.index).padStart(2, "0"), w + h * 0.02, h * 0.48);
  c.restore();

  c.save();
  c.translate(w * 0.5, h * 0.5);
  c.rotate(-0.42);
  c.fillStyle = alpha(accent, 0.05);
  c.fillRect(-w, -h * 0.07, w * 2, h * 0.14);
  c.restore();
}

function chrome(c, scene, local, p, w, h, t) {
  const pal = DATA.palette;
  const m = M;
  c.save();
  c.font = font(11 * U, 700, MONO);
  c.fillStyle = alpha(pal.ink, 0.62);
  c.textBaseline = "middle";
  c.textAlign = "left";
  c.fillText(String(DATA.title || "").toUpperCase().slice(0, 52), m, m * 0.55);
  c.textAlign = "right";
  c.fillText(String(DATA.category || "").toUpperCase(), w - m, m * 0.55);

  const y = h - m * 0.55;
  c.fillStyle = alpha(pal.ink, 0.14);
  c.fillRect(m, y, w - m * 2, Math.max(1.5, 1.5 * U));
  const progress = DATA.duration > 0 ? clamp(t / DATA.duration) : 0;
  c.fillStyle = scene.accent || pal.signal;
  c.fillRect(m, y, (w - m * 2) * progress, Math.max(1.5, 1.5 * U));
  c.fillStyle = alpha(pal.ink, 0.3);
  for (const item of DATA.scenes) {
    const x = m + (w - m * 2) * (item.start / Math.max(0.001, DATA.duration));
    c.fillRect(x, y - 4 * U, Math.max(1, U), 9 * U);
  }
  c.font = font(10.5 * U, 700, MONO);
  c.fillStyle = alpha(pal.ink, 0.55);
  c.textAlign = "right";
  c.fillText(`${String(scene.index).padStart(2, "0")} / ${String(DATA.scenes.length).padStart(2, "0")}`, w - m, y - 15 * U);
  c.restore();
}

function layoutSplit(c, scene, local, p, w, h) {
  const pal = DATA.palette;
  const accent = scene.accent || pal.signal;
  const portrait = h > w * 1.02;
  const m = M;
  const textW = portrait ? w - m * 2 : w * 0.47;
  const appear = spring(clamp(local / 0.75));
  const titleY = portrait ? h * 0.17 : h * 0.23;
  drawKicker(c, scene.kicker || `SCENE ${String(scene.index).padStart(2, "0")}`, m, titleY - 34 * U, alpha(pal.ink, 0.72), accent, 12 * U);
  const bottom = drawTitle(c, scene.title, m, titleY, textW, portrait ? 3 : 4, h * (portrait ? 0.092 : 0.105), h * 0.045, pal.ink, {
    upper: DATA.style === "swiss" || DATA.style === "cinematic",
    reveal: appear,
  });
  c.save();
  c.fillStyle = accent;
  c.fillRect(m, bottom + 20 * U, Math.min(textW * 0.22, 120 * U) * appear, Math.max(3, 4 * U));
  c.restore();
  if (DATA.showCaptions && scene.narration) {
    drawBody(c, scene.narration, m, bottom + 38 * U, textW, portrait ? 4 : 5, h * (portrait ? 0.031 : 0.028), alpha(pal.ink, 0.78));
  }
  if (portrait) {
    drawCard(c, scene, m, h * 0.58, w - m * 2, h * 0.28, local, p, 24 * U, 0, appear);
  } else {
    drawCard(c, scene, w * 0.56, h * 0.16, w * 0.37, h * 0.62, local, p, 24 * U, 0.012 * (1 - appear), appear);
  }
}

function layoutFull(c, scene, local, p, w, h) {
  const pal = DATA.palette;
  const accent = scene.accent || pal.signal;
  const image = scene.asset ? images.get(scene.asset) : null;
  if (image) {
    const zoom = 1.06 + p * 0.07;
    drawImageCover(c, image, 0, 0, w, h, zoom, (scene.index % 2 ? 1 : -1) * 0.012 * p, -0.012 * p);
  } else {
    drawAbstract(c, 0, 0, w, h, scene.index + 4, accent, 0);
  }
  const shade = c.createLinearGradient(0, 0, 0, h);
  shade.addColorStop(0, "rgba(0,0,0,0.12)");
  shade.addColorStop(0.45, "rgba(0,0,0,0.36)");
  shade.addColorStop(1, "rgba(0,0,0,0.88)");
  c.fillStyle = shade;
  c.fillRect(0, 0, w, h);
  const side = c.createLinearGradient(0, 0, w * 0.72, 0);
  side.addColorStop(0, "rgba(0,0,0,0.62)");
  side.addColorStop(1, "rgba(0,0,0,0)");
  c.fillStyle = side;
  c.fillRect(0, 0, w, h);

  const m = M;
  const appear = spring(clamp(local / 0.8));
  drawKicker(c, scene.kicker || `SCENE ${String(scene.index).padStart(2, "0")}`, m, h * 0.55 - 44 * U, "rgba(255,255,255,0.82)", accent, 12 * U);
  const bottom = drawTitle(c, scene.title, m, h * 0.58, w * 0.68, 3, h * 0.115, h * 0.05, "#ffffff", {
    upper: DATA.style === "swiss" || DATA.style === "cinematic",
    reveal: appear,
  });
  c.fillStyle = accent;
  c.fillRect(m, bottom + 18 * U, Math.min(130 * U, w * 0.12) * appear, Math.max(3, 4 * U));
  if (DATA.showCaptions && scene.narration) {
    drawBody(c, scene.narration, m, bottom + 34 * U, w * 0.58, 3, h * 0.03, "rgba(255,255,255,0.82)");
  }
}

function layoutMinimal(c, scene, local, p, w, h) {
  const pal = DATA.palette;
  const accent = scene.accent || pal.signal;
  const m = M;
  const portrait = h > w * 1.02;
  const appear = spring(clamp(local / 0.85));
  drawKicker(c, scene.kicker || `SCENE ${String(scene.index).padStart(2, "0")}`, m, h * 0.18, alpha(pal.ink, 0.62), accent, 12 * U);
  const maxW = portrait ? w - m * 2 : w * 0.7;
  const bottom = drawTitle(c, scene.title, m, h * (portrait ? 0.23 : 0.25), maxW, 4, h * (portrait ? 0.11 : 0.14), h * 0.055, pal.ink, {
    upper: false,
    reveal: appear,
    weight: 800,
  });
  c.save();
  c.strokeStyle = alpha(pal.ink, 0.18);
  c.lineWidth = Math.max(1, U);
  c.beginPath();
  c.moveTo(m, bottom + 30 * U);
  c.lineTo(w - m, bottom + 30 * U);
  c.stroke();
  c.restore();
  if (DATA.showCaptions && scene.narration) {
    drawBody(c, scene.narration, m, bottom + 52 * U, portrait ? w - m * 2 : w * 0.54, 5, h * 0.03, alpha(pal.ink, 0.72));
  }
  const stripH = portrait ? h * 0.18 : h * 0.2;
  const stripY = h - m * 1.4 - stripH;
  const image = scene.asset ? images.get(scene.asset) : null;
  c.save();
  roundRect(c, m, stripY, w - m * 2, stripH, 18 * U);
  c.clip();
  if (image) {
    drawImageCover(c, image, m, stripY, w - m * 2, stripH, 1.04 + p * 0.04, 0.01 * p, 0);
    c.fillStyle = "rgba(0,0,0,0.18)";
    c.fillRect(m, stripY, w - m * 2, stripH);
  } else {
    drawAbstract(c, m, stripY, w - m * 2, stripH, scene.index + 9, accent, 0);
  }
  c.restore();
}

function extractNumber(text) {
  const match = String(text || "").match(/(\d[\d,.]*)/);
  if (!match) return null;
  const n = Number(match[1].replace(/,/g, ""));
  return Number.isFinite(n) ? { value: n, raw: match[1] } : null;
}

function layoutData(c, scene, local, p, w, h) {
  const pal = DATA.palette;
  const accent = scene.accent || pal.signal;
  const m = M;
  const portrait = h > w * 1.02;
  const appear = spring(clamp(local / 0.8));
  const stat = scene.stat || extractNumber(scene.narration) || { value: scene.index + 1, raw: String(scene.index + 1) };
  const statValue = Math.round(lerp(0, stat.value, eo(clamp(local / 1.1))));
  const statText = String(stat.raw || stat.value).replace(/[^\d.,%+]/g, "") || String(statValue);
  const shown = stat.value >= 10 ? String(statValue) : statText;

  drawKicker(c, scene.kicker || "THE SIGNAL", m, h * 0.18, alpha(pal.ink, 0.68), accent, 12 * U);
  const titleW = portrait ? w - m * 2 : w * 0.52;
  const bottom = drawTitle(c, scene.title, m, h * (portrait ? 0.23 : 0.24), titleW, 3, h * (portrait ? 0.09 : 0.1), h * 0.048, pal.ink, {
    upper: true,
    reveal: appear,
  });

  c.save();
  c.globalAlpha = clamp(appear);
  c.textAlign = "right";
  c.textBaseline = "alphabetic";
  c.fillStyle = accent;
  c.font = font(h * (portrait ? 0.15 : 0.22), 900, DISPLAY);
  c.fillText(shown, w - m, portrait ? h * 0.48 : h * 0.45);
  c.font = font(12 * U, 700, MONO);
  c.fillStyle = alpha(pal.ink, 0.62);
  c.fillText("MEASURED SIGNAL", w - m, (portrait ? h * 0.48 : h * 0.45) + 24 * U);
  c.restore();

  const chartX = m;
  const chartY = portrait ? h * 0.56 : h * 0.58;
  const chartW = portrait ? w - m * 2 : w * 0.52;
  const chartH = portrait ? h * 0.16 : h * 0.2;
  const rnd = mulberry(scene.index * 53 + 7);
  const bars = Array.from({ length: 9 }, () => 0.18 + rnd() * 0.82);
  c.save();
  c.strokeStyle = alpha(pal.ink, 0.1);
  c.lineWidth = Math.max(1, U);
  for (let i = 0; i <= 3; i++) {
    const y = chartY + (chartH / 3) * i;
    c.beginPath();
    c.moveTo(chartX, y);
    c.lineTo(chartX + chartW, y);
    c.stroke();
  }
  const gap = chartW / bars.length;
  bars.forEach((value, index) => {
    const grow = eo(seg(local, 0.15 + index * 0.045, 0.65 + index * 0.045));
    const bh = chartH * value * grow;
    c.fillStyle = index === bars.length - 2 ? accent : alpha(pal.ink, 0.18);
    c.fillRect(chartX + index * gap + gap * 0.16, chartY + chartH - bh, gap * 0.68, bh);
  });
  c.restore();

  if (DATA.showCaptions && scene.narration) {
    drawBody(c, scene.narration, m, chartY + chartH + 26 * U, portrait ? w - m * 2 : w * 0.54, 4, h * 0.029, alpha(pal.ink, 0.76));
  }
}

function layoutCollage(c, scene, local, p, w, h) {
  const pal = DATA.palette;
  const accent = scene.accent || pal.signal;
  const m = M;
  const portrait = h > w * 1.02;
  const appear = spring(clamp(local / 0.9));
  const titleW = portrait ? w - m * 2 : w * 0.44;
  drawKicker(c, scene.kicker || "FIELD NOTES", m, h * 0.17, alpha(pal.ink, 0.65), accent, 12 * U);
  const bottom = drawTitle(c, scene.title, m, h * (portrait ? 0.22 : 0.23), titleW, 3, h * (portrait ? 0.088 : 0.1), h * 0.046, pal.ink, {
    upper: DATA.style === "swiss",
    reveal: appear,
  });
  if (DATA.showCaptions && scene.narration) {
    drawBody(c, scene.narration, m, bottom + 34 * U, titleW, 4, h * 0.029, alpha(pal.ink, 0.75));
  }

  const cx = portrait ? w * 0.5 : w * 0.72;
  const cy = portrait ? h * 0.68 : h * 0.5;
  const cardW = portrait ? w * 0.62 : w * 0.33;
  const cardH = portrait ? h * 0.2 : h * 0.48;
  const drift = 1 - appear;
  drawCard(c, scene, cx - cardW * 0.5, cy - cardH * 0.5, cardW, cardH, local, p, 22 * U, 0.035 * drift, appear);
  c.save();
  c.globalAlpha = 0.55 * appear;
  c.translate(cx + cardW * 0.22, cy - cardH * 0.4);
  c.rotate(0.11 + 0.02 * drift);
  c.fillStyle = accent;
  c.fillRect(-cardW * 0.2, -cardH * 0.2, cardW * 0.4, cardH * 0.4);
  c.restore();
  c.save();
  c.globalAlpha = 0.4 * appear;
  c.translate(cx - cardW * 0.35, cy + cardH * 0.35);
  c.rotate(-0.09 - 0.02 * drift);
  c.strokeStyle = alpha(pal.ink, 0.5);
  c.lineWidth = Math.max(1, U * 1.5);
  c.strokeRect(-cardW * 0.18, -cardH * 0.18, cardW * 0.36, cardH * 0.36);
  c.restore();
}

function layoutQuote(c, scene, local, p, w, h) {
  const pal = DATA.palette;
  const accent = scene.accent || pal.signal;
  const m = M;
  const appear = spring(clamp(local / 0.85));
  const portrait = h > w * 1.02;
  c.save();
  c.globalAlpha = 0.18 * appear;
  c.fillStyle = accent;
  c.font = font(h * 0.42, 900, SERIF);
  c.textBaseline = "top";
  c.fillText("“", m, h * 0.13);
  c.restore();
  drawKicker(c, scene.kicker || "THE TAKEAWAY", m, h * 0.16, alpha(pal.ink, 0.65), accent, 12 * U);
  const quote = scene.narration || scene.title;
  const quoteW = portrait ? w - m * 2 : w * 0.74;
  c.save();
  c.globalAlpha = clamp(appear);
  c.font = font(h * (portrait ? 0.052 : 0.062), 700, SERIF);
  c.fillStyle = pal.ink;
  c.textBaseline = "top";
  const lines = wrap(c, quote, quoteW, c.font).slice(0, 4);
  const lineH = h * (portrait ? 0.068 : 0.078);
  lines.forEach((line, i) => c.fillText(line, m, h * 0.26 + i * lineH));
  c.restore();
  c.fillStyle = accent;
  c.fillRect(m, h * 0.82, Math.min(160 * U, w * 0.18) * appear, Math.max(3, 4 * U));
  drawTitle(c, scene.title, m, h * 0.86, quoteW, 1, h * 0.03, h * 0.022, alpha(pal.ink, 0.62), {
    upper: true,
    reveal: appear,
    weight: 700,
  });
}

function layoutIsometric(c, scene, local, p, w, h) {
  const pal = DATA.palette;
  const accent = scene.accent || pal.signal;
  const m = M;
  const portrait = h > w * 1.02;
  const appear = spring(clamp(local / 0.8));
  const panelW = portrait ? w * 0.88 : w * 0.42;
  const panelH = portrait ? h * 0.34 : h * 0.5;
  const px = portrait ? m : m;
  const py = portrait ? h * 0.12 : h * 0.24;
  c.save();
  c.globalAlpha = 0.86 * appear;
  const grad = c.createLinearGradient(px, py, px + panelW, py + panelH);
  grad.addColorStop(0, alpha(pal.bg, 0.92));
  grad.addColorStop(1, alpha(pal.bg, 0.18));
  c.fillStyle = grad;
  roundRect(c, px, py, panelW, panelH, 18 * U);
  c.fill();
  c.strokeStyle = alpha(accent, 0.36);
  c.lineWidth = Math.max(1, U);
  roundRect(c, px + 0.5, py + 0.5, panelW - 1, panelH - 1, 18 * U);
  c.stroke();
  c.restore();

  drawKicker(c, scene.kicker || "SYSTEM VIEW", m + 22 * U, py + 28 * U, alpha(pal.ink, 0.78), accent, 12 * U);
  const bottom = drawTitle(
    c,
    scene.title,
    m + 22 * U,
    py + 58 * U,
    panelW - 44 * U,
    portrait ? 3 : 4,
    h * (portrait ? 0.07 : 0.082),
    h * 0.04,
    pal.ink,
    { upper: true, reveal: appear },
  );
  const stat = scene.stat || { value: scene.index + 1, raw: String(scene.index + 1) };
  c.save();
  c.globalAlpha = clamp(appear);
  c.fillStyle = accent;
  c.font = font(h * (portrait ? 0.09 : 0.1), 900, DISPLAY);
  c.textAlign = "left";
  c.textBaseline = "alphabetic";
  c.fillText(String(stat.raw || stat.value), m + 22 * U, bottom + h * 0.11);
  c.font = font(11 * U, 700, MONO);
  c.fillStyle = alpha(pal.ink, 0.62);
  c.fillText("MODELLED SIGNAL", m + 22 * U, bottom + h * 0.13);
  c.restore();
  if (DATA.showCaptions && scene.narration) {
    drawBody(c, scene.narration, m + 22 * U, bottom + h * 0.16, panelW - 44 * U, 3, h * 0.026, alpha(pal.ink, 0.72));
  }
  const labels = ["STRUCTURE", "FLOW", "SIGNAL"];
  c.save();
  c.globalAlpha = 0.72 * appear;
  c.font = font(10 * U, 700, MONO);
  c.textAlign = "right";
  c.fillStyle = alpha(pal.ink, 0.62);
  labels.forEach((label, index) => {
    c.fillText(`${String(index + 1).padStart(2, "0")}  ${label}`, w - m, h * 0.24 + index * 22 * U);
  });
  c.restore();
}

function layoutTypographic(c, scene, local, p, w, h) {
  const pal = DATA.palette;
  const accent = scene.accent || pal.signal;
  const m = M;
  const portrait = h > w * 1.02;
  const appear = spring(clamp(local / 0.7));
  const words = String(scene.title || "").toUpperCase().split(/\s+/).filter(Boolean);
  const titleW = portrait ? w - m * 2 : w * 0.84;
  drawKicker(c, scene.kicker || "TYPE / MOTION", m, h * 0.15, alpha(pal.ink, 0.6), accent, 12 * U);
  const fitted = fitTitle(c, words.join(" "), titleW, portrait ? 5 : 4, h * (portrait ? 0.13 : 0.18), h * 0.06, 900);
  let y = h * (portrait ? 0.23 : 0.24);
  const lineH = fitted.size * 0.96;
  c.save();
  fitted.lines.forEach((line, index) => {
    const reveal = spring(clamp((local - index * 0.12) / 0.7));
    c.save();
    c.beginPath();
    c.rect(m - 6 * U, y - fitted.size * 0.1, (titleW + 12 * U) * reveal, lineH + fitted.size * 0.25);
    c.clip();
    c.globalAlpha = clamp(reveal * 1.3);
    c.font = fitted.font;
    c.fillStyle = index === fitted.lines.length - 1 ? accent : pal.ink;
    c.textAlign = "left";
    c.textBaseline = "top";
    c.fillText(line, m, y);
    c.restore();
    y += lineH;
  });
  c.restore();
  c.save();
  c.fillStyle = accent;
  c.fillRect(m, y + 12 * U, Math.min(150 * U, w * 0.14) * appear, Math.max(3, 4 * U));
  c.restore();
  if (DATA.showCaptions && scene.narration) {
    drawBody(c, scene.narration, m, y + 34 * U, portrait ? w - m * 2 : w * 0.58, 4, h * 0.028, alpha(pal.ink, 0.74));
  }
  c.save();
  c.globalAlpha = 0.08;
  c.fillStyle = pal.ink;
  c.font = font(h * 0.62, 900, DISPLAY);
  c.textAlign = "right";
  c.textBaseline = "middle";
  c.fillText(String(scene.index).padStart(2, "0"), w + h * 0.02, h * 0.52);
  c.restore();
}

function layoutInfographic(c, scene, local, p, w, h) {
  const pal = DATA.palette;
  const accent = scene.accent || pal.signal;
  const m = M;
  const portrait = h > w * 1.02;
  const appear = spring(clamp(local / 0.8));
  const stat = scene.stat || { value: scene.index + 1, raw: String(scene.index + 1) };
  const chart = Array.isArray(scene.chart) && scene.chart.length ? scene.chart : [0.25, 0.45, 0.35, 0.62, 0.5, 0.78, 0.58, 0.9, 0.7];
  drawKicker(c, scene.kicker || "INFOGRAPHIC", m, h * 0.15, alpha(pal.ink, 0.64), accent, 12 * U);
  const titleW = portrait ? w - m * 2 : w * 0.5;
  drawTitle(c, scene.title, m, h * (portrait ? 0.2 : 0.21), titleW, 3, h * (portrait ? 0.085 : 0.095), h * 0.045, pal.ink, {
    upper: true,
    reveal: appear,
  });
  const cx = portrait ? w * 0.5 : w * 0.72;
  const cy = portrait ? h * 0.53 : h * 0.46;
  const radius = Math.min(w, h) * (portrait ? 0.15 : 0.18);
  c.save();
  c.lineWidth = Math.max(8, 16 * U);
  c.strokeStyle = alpha(pal.ink, 0.12);
  c.beginPath();
  c.arc(cx, cy, radius, 0, Math.PI * 2);
  c.stroke();
  c.strokeStyle = accent;
  c.lineCap = "round";
  c.beginPath();
  c.arc(cx, cy, radius, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * 0.72 * eo(clamp(local / 1.2)));
  c.stroke();
  c.textAlign = "center";
  c.textBaseline = "middle";
  c.fillStyle = pal.ink;
  c.font = font(radius * 0.48, 900, DISPLAY);
  c.fillText(String(stat.raw || stat.value), cx, cy - radius * 0.04);
  c.font = font(10 * U, 700, MONO);
  c.fillStyle = alpha(pal.ink, 0.6);
  c.fillText("PRIMARY METRIC", cx, cy + radius * 0.42);
  c.restore();
  const chartX = m;
  const chartY = portrait ? h * 0.72 : h * 0.65;
  const chartW = portrait ? w - m * 2 : w * 0.48;
  const chartH = portrait ? h * 0.1 : h * 0.16;
  c.save();
  const gap = chartW / chart.length;
  chart.forEach((value, index) => {
    const grow = eo(seg(local, 0.12 + index * 0.04, 0.55 + index * 0.04));
    const bh = chartH * value * grow;
    c.fillStyle = index === chart.length - 2 ? accent : alpha(pal.ink, 0.2);
    c.fillRect(chartX + index * gap + gap * 0.14, chartY + chartH - bh, gap * 0.7, bh);
  });
  c.restore();
  if (DATA.showCaptions && scene.narration) {
    drawBody(c, scene.narration, m, chartY + chartH + 24 * U, portrait ? w - m * 2 : w * 0.55, 3, h * 0.027, alpha(pal.ink, 0.74));
  }
}

function layoutWalkthrough(c, scene, local, p, w, h) {
  const pal = DATA.palette;
  const accent = scene.accent || pal.signal;
  const m = M;
  const portrait = h > w * 1.02;
  const appear = spring(clamp(local / 0.8));
  const image = scene.asset ? images.get(scene.asset) : null;
  const panelX = portrait ? m : w * 0.2;
  const panelY = portrait ? h * 0.3 : h * 0.18;
  const panelW = portrait ? w - m * 2 : w * 0.64;
  const panelH = portrait ? h * 0.42 : h * 0.6;
  drawKicker(c, scene.kicker || "PRODUCT WALKTHROUGH", m, h * 0.13, alpha(pal.ink, 0.64), accent, 12 * U);
  drawTitle(c, scene.title, m, h * 0.16, portrait ? w - m * 2 : w * 0.54, 2, h * 0.075, h * 0.04, pal.ink, {
    upper: true,
    reveal: appear,
  });
  c.save();
  c.globalAlpha = 0.94 * appear;
  c.shadowColor = "rgba(0,0,0,0.5)";
  c.shadowBlur = 40 * U;
  c.shadowOffsetY = 24 * U;
  roundRect(c, panelX, panelY, panelW, panelH, 18 * U);
  c.fillStyle = pal.panel;
  c.fill();
  c.shadowColor = "transparent";
  roundRect(c, panelX, panelY, panelW, panelH, 18 * U);
  c.clip();
  c.fillStyle = mix(pal.panel, pal.bg, 0.35);
  c.fillRect(panelX, panelY, panelW, 42 * U);
  ["#ff5f57", "#febc2e", "#28c840"].forEach((color, index) => {
    c.fillStyle = color;
    c.beginPath();
    c.arc(panelX + 22 * U + index * 16 * U, panelY + 21 * U, 4.5 * U, 0, Math.PI * 2);
    c.fill();
  });
  c.fillStyle = alpha(pal.ink, 0.1);
  roundRect(c, panelX + panelW * 0.3, panelY + 12 * U, panelW * 0.4, 18 * U, 9 * U);
  c.fill();
  c.fillStyle = mix(pal.bg, pal.panel, 0.18);
  c.fillRect(panelX, panelY + 42 * U, panelW * 0.24, panelH - 42 * U);
  const rows = ["OVERVIEW", "PIPELINE", "REPORTS", "SETTINGS"];
  c.font = font(10 * U, 700, MONO);
  rows.forEach((row, index) => {
    const active = index === Math.min(rows.length - 1, Math.floor(seg(local, 0.3, 1) * rows.length));
    c.fillStyle = active ? alpha(accent, 0.18) : "transparent";
    c.fillRect(panelX + 12 * U, panelY + 68 * U + index * 34 * U, panelW * 0.24 - 24 * U, 26 * U);
    c.fillStyle = active ? accent : alpha(pal.ink, 0.48);
    c.fillText(row, panelX + 24 * U, panelY + 84 * U + index * 34 * U);
  });
  const screenX = panelX + panelW * 0.28;
  const screenY = panelY + 60 * U;
  const screenW = panelW * 0.68;
  const screenH = panelH - 78 * U;
  if (image) {
    drawImageCover(c, image, screenX, screenY, screenW, screenH, 1.04 + p * 0.05, 0, 0);
    c.fillStyle = "rgba(0,0,0,0.18)";
    c.fillRect(screenX, screenY, screenW, screenH);
  } else {
    drawAbstract(c, screenX, screenY, screenW, screenH, scene.index + 21, accent, 8 * U);
  }
  c.fillStyle = alpha(pal.ink, 0.08);
  for (let index = 0; index < 4; index++) {
    const rowY = screenY + 24 * U + index * (screenH / 5);
    c.fillRect(screenX + 20 * U, rowY, screenW * (0.36 + (index % 2) * 0.2), 8 * U);
    c.fillRect(screenX + 20 * U, rowY + 14 * U, screenW * 0.22, 5 * U);
  }
  const cursor = eo(seg(local, 0.5, 1.6));
  c.fillStyle = accent;
  c.beginPath();
  const cursorX = screenX + screenW * (0.35 + cursor * 0.28);
  const cursorY = screenY + screenH * (0.48 + cursor * 0.16);
  c.moveTo(cursorX, cursorY);
  c.lineTo(cursorX + 12 * U, cursorY + 26 * U);
  c.lineTo(cursorX + 4 * U, cursorY + 24 * U);
  c.lineTo(cursorX + 1 * U, cursorY + 34 * U);
  c.closePath();
  c.fill();
  c.restore();
  if (DATA.showCaptions && scene.narration) {
    drawBody(c, scene.narration, m, panelY + panelH + 24 * U, portrait ? w - m * 2 : w * 0.54, 3, h * 0.027, alpha(pal.ink, 0.74));
  }
}

function layoutDocumentary(c, scene, local, p, w, h) {
  const pal = DATA.palette;
  const accent = scene.accent || pal.signal;
  const image = scene.asset ? images.get(scene.asset) : null;
  if (image) {
    drawImageCover(c, image, 0, 0, w, h, 1.05 + p * 0.07, (scene.index % 2 ? 1 : -1) * 0.01 * p, -0.008 * p);
  } else {
    drawAbstract(c, 0, 0, w, h, scene.index + 31, accent, 0);
  }
  const shade = c.createLinearGradient(0, h * 0.2, 0, h);
  shade.addColorStop(0, "rgba(0,0,0,0.04)");
  shade.addColorStop(0.55, "rgba(0,0,0,0.24)");
  shade.addColorStop(1, "rgba(0,0,0,0.9)");
  c.fillStyle = shade;
  c.fillRect(0, 0, w, h);
  const m = M;
  const appear = spring(clamp(local / 0.9));
  c.save();
  c.globalAlpha = 0.8 * appear;
  c.fillStyle = "rgba(0,0,0,0.34)";
  roundRect(c, m, h * 0.66, w - m * 2, h * 0.22, 12 * U);
  c.fill();
  c.fillStyle = accent;
  c.fillRect(m, h * 0.66, Math.max(4, 5 * U), h * 0.22);
  c.restore();
  drawKicker(c, scene.kicker || "DOCUMENTARY", m + 20 * U, h * 0.69, "rgba(255,255,255,0.72)", accent, 11 * U);
  drawTitle(c, scene.title, m + 20 * U, h * 0.72, w * 0.7, 2, h * 0.075, h * 0.042, "#ffffff", {
    upper: true,
    reveal: appear,
  });
  if (DATA.showCaptions && scene.narration) {
    drawBody(c, scene.narration, m + 20 * U, h * 0.81, w * 0.62, 2, h * 0.025, "rgba(255,255,255,0.74)");
  }
  c.save();
  c.font = font(10 * U, 700, MONO);
  c.fillStyle = "rgba(255,255,255,0.48)";
  c.textAlign = "right";
  c.textBaseline = "middle";
  c.fillText(`REC  ${String(scene.index).padStart(2, "0")}:${String(Math.floor(local)).padStart(2, "0")}`, w - m, h * 0.12);
  c.restore();
}

function layoutStory(c, scene, local, p, w, h) {
  const pal = DATA.palette;
  const accent = scene.accent || pal.signal;
  const m = M;
  const portrait = h > w * 1.02;
  const appear = spring(clamp(local / 0.85));
  drawKicker(c, scene.kicker || "CHAPTER", m, h * 0.16, alpha(pal.ink, 0.6), accent, 12 * U);
  c.save();
  c.globalAlpha = 0.14 * appear;
  c.fillStyle = accent;
  c.font = font(h * 0.34, 900, SERIF);
  c.textAlign = "left";
  c.textBaseline = "top";
  c.fillText(String(scene.index).padStart(2, "0"), m - 6 * U, h * 0.18);
  c.restore();
  const titleW = portrait ? w - m * 2 : w * 0.48;
  const bottom = drawTitle(c, scene.title, m, h * (portrait ? 0.3 : 0.28), titleW, 4, h * (portrait ? 0.085 : 0.1), h * 0.045, pal.ink, {
    upper: false,
    reveal: appear,
    weight: 800,
  });
  c.save();
  c.fillStyle = accent;
  c.fillRect(m, bottom + 18 * U, Math.min(120 * U, w * 0.12) * appear, Math.max(3, 4 * U));
  c.restore();
  if (DATA.showCaptions && scene.narration) {
    drawBody(c, scene.narration, m, bottom + 36 * U, portrait ? w - m * 2 : w * 0.42, 5, h * 0.028, alpha(pal.ink, 0.74));
  }
  const cardW = portrait ? w * 0.58 : w * 0.32;
  const cardH = portrait ? h * 0.2 : h * 0.52;
  const cardX = portrait ? w - m - cardW : w - m - cardW;
  const cardY = portrait ? h * 0.7 : h * 0.22;
  drawCard(c, scene, cardX, cardY, cardW, cardH, local, p, 18 * U, -0.025 * (1 - appear), appear);
}

function renderScene(c, scene, local, p, w, h, t) {
  const pal = DATA.palette;
  c.save();
  c.textAlign = "left";
  c.textBaseline = "top";
  const isometric = (scene.layout === "isometric" || scene.pattern === "isometric") && three;
  if (!isometric) backdrop(c, scene, local, p, w, h);
  c.save();
  const camera = scene.camera || "static";
  const push = clamp(p);
  if (camera === "push-in") {
    c.translate(w / 2, h / 2);
    c.scale(1 + push * 0.035, 1 + push * 0.035);
    c.translate(-w / 2, -h / 2);
  } else if (camera === "pull-out") {
    c.translate(w / 2, h / 2);
    c.scale(1.06 - push * 0.045, 1.06 - push * 0.045);
    c.translate(-w / 2, -h / 2);
  } else if (camera === "pan-left") {
    c.translate(-w * 0.03 * push, 0);
  } else if (camera === "pan-right") {
    c.translate(w * 0.03 * push, 0);
  } else if (camera === "orbit") {
    c.translate(w / 2, h / 2);
    c.rotate(Math.sin(push * Math.PI) * 0.008);
    c.translate(-w / 2, -h / 2);
  } else if (camera === "tilt") {
    c.translate(0, -h * 0.02 * push);
  }
  switch (scene.layout) {
    case "full":
      layoutFull(c, scene, local, p, w, h);
      break;
    case "minimal":
      layoutMinimal(c, scene, local, p, w, h);
      break;
    case "data":
      layoutData(c, scene, local, p, w, h);
      break;
    case "collage":
      layoutCollage(c, scene, local, p, w, h);
      break;
    case "quote":
      layoutQuote(c, scene, local, p, w, h);
      break;
    case "isometric":
      layoutIsometric(c, scene, local, p, w, h);
      break;
    case "typographic":
      layoutTypographic(c, scene, local, p, w, h);
      break;
    case "infographic":
      layoutInfographic(c, scene, local, p, w, h);
      break;
    case "walkthrough":
      layoutWalkthrough(c, scene, local, p, w, h);
      break;
    case "documentary":
      layoutDocumentary(c, scene, local, p, w, h);
      break;
    case "story":
      layoutStory(c, scene, local, p, w, h);
      break;
    default:
      layoutSplit(c, scene, local, p, w, h);
      break;
  }
  c.restore();
  applyEffects(c, scene, local, p, w, h, t);
  chrome(c, scene, local, p, w, h, t);
  c.restore();
}

function drawEndSlate(c, elapsed) {
  const pal = DATA.palette;
  const e = eo(seg(elapsed, 0, 0.45));
  const fade = 1 - eo(seg(elapsed, 0.85, 1.1));
  c.save();
  c.globalAlpha = e * fade;
  c.fillStyle = "rgba(4,6,12,0.78)";
  c.fillRect(0, 0, W, H);
  c.fillStyle = pal.signal;
  c.fillRect(M, H * 0.46, Math.min(90 * U, W * 0.1), Math.max(3, 4 * U));
  c.textAlign = "left";
  c.textBaseline = "top";
  c.fillStyle = "#ffffff";
  c.font = font(H * 0.06, 900, DISPLAY);
  const lines = wrap(c, String(DATA.title || "").toUpperCase(), W - M * 2, c.font).slice(0, 2);
  lines.forEach((line, i) => c.fillText(line, M, H * 0.5 + i * H * 0.068));
  c.font = font(12 * U, 700, MONO);
  c.fillStyle = "rgba(255,255,255,0.62)";
  c.fillText("AI FILM STUDIO  /  " + String(DATA.category || "").toUpperCase(), M, H * 0.72);
  c.restore();
}

function sceneAt(t) {
  for (let i = DATA.scenes.length - 1; i >= 0; i--) {
    if (t >= DATA.scenes[i].start) return i;
  }
  return 0;
}

function draw(t) {
  const idx = sceneAt(t);
  const scene = DATA.scenes[idx];
  const local = Math.max(0, t - scene.start);
  const p = clamp(local / Math.max(0.001, scene.duration));
  const prev = idx > 0 ? DATA.scenes[idx - 1] : null;
  const transDur = Math.min(0.55, Math.max(0.2, scene.duration * 0.12));
  const e = prev ? seg(local, 0, transDur) : 1;
  const isometric = scene.layout === "isometric" || scene.pattern === "isometric";
  const prevIsometric = prev && (prev.layout === "isometric" || prev.pattern === "isometric");
  ctx.clearRect(0, 0, W, H);
  if (isometric && three) {
    renderThree(scene, local, p);
  } else {
    hideThree();
  }
  if (prev && e < 1 && scene.transition !== "cut" && !isometric && !prevIsometric) {
    octx.clearRect(0, 0, W, H);
    renderScene(octx, prev, prev.duration, 1, W, H, prev.start + prev.duration);
    renderScene(ctx, scene, local, p, W, H, t);
    ctx.save();
    if (scene.transition === "fade" || scene.transition === "dissolve" || scene.transition === "blur") {
      ctx.globalAlpha = 1 - e;
      ctx.drawImage(off, 0, 0);
    } else if (scene.transition === "zoom") {
      ctx.globalAlpha = 1 - e;
      ctx.translate(W / 2, H / 2);
      ctx.scale(1 + (1 - e) * 0.06, 1 + (1 - e) * 0.06);
      ctx.translate(-W / 2, -H / 2);
      ctx.drawImage(off, 0, 0);
    } else if (scene.transition === "push") {
      ctx.globalAlpha = 1 - e;
      ctx.drawImage(off, -W * (1 - e) * 0.14, 0);
    } else if (scene.transition === "whip") {
      ctx.globalAlpha = 1 - e;
      ctx.drawImage(off, -W * (1 - e) * 0.55, 0);
    } else if (scene.transition === "iris") {
      ctx.beginPath();
      ctx.arc(W / 2, H / 2, Math.max(1, Math.min(W, H) * 0.72 * e), 0, Math.PI * 2);
      ctx.clip();
      ctx.drawImage(off, 0, 0);
    } else if (scene.transition === "glitch") {
      const rnd = mulberry(Math.floor(t * 18) * 31 + 7);
      ctx.globalAlpha = 0.8;
      for (let i = 0; i < 12; i++) {
        const y = rnd() * H;
        const hh = 2 + rnd() * 22;
        const dx = (rnd() - 0.5) * 22 * (1 - e);
        ctx.drawImage(off, 0, y, W, hh, dx, y, W, hh);
      }
      ctx.globalAlpha = 1 - e;
      ctx.drawImage(off, 0, 0);
    } else {
      ctx.beginPath();
      ctx.rect(W * (1 - e), 0, W * e + 1, H);
      ctx.clip();
      ctx.drawImage(off, 0, 0);
    }
    ctx.restore();
  } else {
    if ((isometric || prevIsometric) && e < 1) {
      ctx.fillStyle = `rgba(0,0,0,${1 - e})`;
      ctx.fillRect(0, 0, W, H);
    }
    renderScene(ctx, scene, local, p, W, H, t);
  }
  if (t > DATA.duration - 1.1) drawEndSlate(ctx, t - (DATA.duration - 1.1));
}

async function boot() {
  const response = await fetch("data.json", { cache: "no-store" });
  DATA = await response.json();
  W = Number(DATA.width) || 1280;
  H = Number(DATA.height) || 720;
  U = Math.min(W, H) / 720;
  M = Math.round(Math.min(W, H) * 0.078);
  canvas.width = W;
  canvas.height = H;
  off.width = W;
  off.height = H;
  canvas.style.width = `${W}px`;
  canvas.style.height = `${H}px`;
  DATA.palette = {
    bg: "#090b12",
    panel: "#121725",
    ink: "#f5f7ff",
    signal: "#ff4d2e",
    accent: "#7c5cff",
    ...(DATA.palette || {}),
  };
  DATA.scenes = (DATA.scenes || []).map((scene, index) => ({
    ...scene,
    index: scene.index || index + 1,
    accent: scene.accent || DATA.palette.signal,
    layout: scene.layout || scene.pattern || "split",
    pattern: scene.pattern || scene.layout || "split",
    camera: scene.camera || "static",
    effects: Array.isArray(scene.effects) ? scene.effects : ["grain", "vignette"],
    transition: scene.transition || "wipe",
  }));

  await initThree();
  await document.fonts.ready.catch(() => {});
  await Promise.all(
    DATA.scenes.map(async (scene) => {
      if (!scene.asset) return;
      const image = new Image();
      image.decoding = "async";
      image.src = scene.asset;
      try {
        await image.decode();
        images.set(scene.asset, image);
      } catch {
        scene.asset = null;
      }
    }),
  );

  window.DUR = Number(DATA.duration) || 1;
  window.render = draw;
  draw(0);
  window.READY = true;
}

boot().catch((error) => {
  console.error("[film] boot failed", error);
  throw error;
});
