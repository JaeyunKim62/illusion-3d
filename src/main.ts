import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { contestRules } from './contestRules.ts';
import './styles.css';

type ViewMode = 'front' | 'right' | 'back' | 'left' | 'reveal' | 'orbit';
type MaskSpec = { name: string; label: string; color: string; imageUrl?: string };
type MaskRows = { spec: MaskSpec; rows: number[][]; rowCount: number; width: number; height: number; activePixels: number };
type RowSummary = { min: number; median: number; max: number };
type RowBalanceStats = {
  activeRows: Readonly<{ front: number; side: number; matched: number }>;
  matchedRowRatio: number;
  rowMismatches: Readonly<{ frontOnly: number; sideOnly: number; emptyBoth: number }>;
  generatedPointsPerMatchedRow: Readonly<RowSummary>;
  activePixels: Readonly<{ front: number; side: number }>;
};
type CloudStats = { points: number; frontCoverage: number; sideCoverage: number; rowsUsed: number; rowCount: number; rowBalance: RowBalanceStats };
type LenticularQa = {
  seed: number;
  maskDimensions: Readonly<{ width: number; height: number; sampleStride: number }>;
  rowCount: number;
  pointCount: number;
  coverage: Readonly<{ front: number; side: number }>;
  rowsUsed: number;
  rowBalance: Readonly<RowBalanceStats>;
  projectionLabels: Readonly<{ front: string; right: string }>;
  scenePointsCount: number;
  pointCloudUsesSharedGeometry: boolean;
  geometryAttributes: Readonly<{
    names: readonly string[];
    positionCount: number;
    positionItemSize: number;
    colorCount: number;
    colorItemSize: number;
  }>;
  visualStyle: Readonly<{
    colorSource: 'fixed-per-point-attribute';
    shaderGlowOnly: boolean;
    viewDependentOpacityGate: boolean;
    depthTestReadingGate: boolean;
  }>;
  pointCloudInvariantHolds: boolean;
};

declare global {
  interface Window {
    __LENTICULAR_QA__: LenticularQa;
  }
}

type GeneratedCloud = {
  positions: Float32Array;
  colors: Float32Array;
  stats: CloudStats;
};

const app = document.querySelector<HTMLDivElement>('#app');
if (!app) throw new Error('Missing #app root');

const MASK_WIDTH = 960;
const MASK_HEIGHT = 280;
const ROW_COUNT = 150;
const SAMPLE_STRIDE = 2;
const POINT_SCALE_X = 3.3;
const POINT_SCALE_Y = 1.2;
const POINT_SCALE_Z = 3.3;
const POINT_SIZE = 3.8;
const VIEW_HALF_HEIGHT = 1.75;
const FRONT_SPEC: MaskSpec = {
  name: 'Front +Z',
  label: 'GOOSE',
  color: '#e8f6ff',
  imageUrl: '/artifacts/reference-image/goose.jpg',
};
const SIDE_SPEC: MaskSpec = {
  name: 'Right +X',
  label: 'NUBZUKI',
  color: '#fff3b0',
  imageUrl: '/artifacts/reference-image/nubzuki.jpg',
};
const RNG_SEED = 4792026;

app.innerHTML = `
  <main class="app-shell">
    <section class="viewer-card">
      <canvas id="scene" aria-label="Shared 3D lenticular point cloud viewer"></canvas>
      <div class="hud">
        <div><b id="phaseLabel">FRONT +Z</b><span id="phaseDetail">same points project to GOOSE reference image</span></div>
        <div class="metric" id="errorMetric">generating shared point cloud…</div>
      </div>
      <div class="view-badge" id="viewBadge">GOOSE</div>
      <div class="story-strip" aria-hidden="true">
        <span><b>1</b> one shared BufferGeometry</span>
        <span><b>2</b> front projection: x,y → goose image</span>
        <span><b>3</b> side projection: z,y → nubzuki image</span>
      </div>
    </section>
    <aside class="panel">
      <p class="eyebrow">KAIST 3D Rendering Contest / 3D Lenticular Point Cloud</p>
      <h1>One Cloud, Multiple Readings</h1>
      <p class="lead">이 브랜치는 글자 대신 <code>artifacts/reference-image</code>의 두 참조 이미지를 사용합니다. 두 이미지는 별도 billboard가 아니라 <b>동일한 점 하나하나</b>의 좌표 <code>(x,y,z)</code>를 공유합니다. 정면 정사영은 <code>(x,y)</code>로 <b>goose</b>, 우측 정사영은 <code>(z,y)</code>로 <b>nubzuki</b> 이미지를 형성합니다.</p>
      <div class="actions">
        <button id="frontBtn" data-mode="front">Front +Z: goose</button>
        <button id="rightBtn" data-mode="right">Right +X: nubzuki</button>
        <button id="backBtn" data-mode="back">Back −Z: mirrored A</button>
        <button id="leftBtn" data-mode="left">Left −X: mirrored B</button>
        <button id="revealBtn" data-mode="reveal">3D reveal</button>
        <button id="orbitBtn" data-mode="orbit">자유 Orbit</button>
        <button id="shotBtn">PNG 캡처</button>
        <button id="recordBtn">10초 WebM 녹화</button>
      </div>
      <p class="hint" id="overlayHelp">Orthographic canonical views only: no opacity gating, no second point set, no hidden duplicate text. Rotate/reveal to inspect the single physical point cloud.</p>
      <p class="capture-status" id="captureStatus" role="status">Capture ready. Use Front/Right before PNG capture, or record a 10s rotation.</p>
      <section class="score-card"><h2>Invariant QA</h2><p class="qa-metric" id="invariantQaMetric">checking physical point-set invariant…</p></section>
      <section class="score-card"><h2>수학적 정의</h2><ul><li>점 하나: <code>p=(x,y,z)</code></li><li>Front +Z projection: <code>πZ(p)=(x,y)</code> → goose reference mask</li><li>Right +X projection: <code>πX(p)=(z,y)</code> → nubzuki reference mask</li><li>Back/Left는 같은 점의 좌우반전 projection</li></ul></section>
      <section class="score-card"><h2>색/빛 단계</h2><ul><li>Geometry는 그대로 하나의 <code>BufferGeometry</code>입니다.</li><li>각 점은 고정된 per-point color attribute를 가집니다.</li><li>cyan→magenta→gold palette와 radial glow shader만 추가했고, view별 geometry/opacity gate는 추가하지 않았습니다.</li></ul></section>
      <section class="score-card"><h2>우선 규정</h2><ul>${contestRules.map((r) => `<li><b>${r.title}</b> — ${r.implementationPolicy}</li>`).join('')}</ul></section>
    </aside>
  </main>
`;

function seeded(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (1664525 * s + 1013904223) >>> 0;
    return s / 0xffffffff;
  };
}

function shuffleInPlace<T>(items: T[], rand: () => number) {
  for (let i = items.length - 1; i > 0; i -= 1) {
    const j = Math.floor(rand() * (i + 1));
    [items[i], items[j]] = [items[j], items[i]];
  }
}

function summarizeCounts(counts: number[]): RowSummary {
  if (counts.length === 0) return { min: 0, median: 0, max: 0 };
  const sorted = [...counts].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  const median = sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
  return { min: sorted[0], median, max: sorted[sorted.length - 1] };
}

function analyzeRowBalance(front: MaskRows, side: MaskRows): RowBalanceStats {
  let frontActiveRows = 0;
  let sideActiveRows = 0;
  let matchedRows = 0;
  let frontOnly = 0;
  let sideOnly = 0;
  let emptyBoth = 0;
  const generatedCounts: number[] = [];

  for (let row = 0; row < ROW_COUNT; row += 1) {
    const frontCount = front.rows[row].length;
    const sideCount = side.rows[row].length;
    const hasFront = frontCount > 0;
    const hasSide = sideCount > 0;
    if (hasFront) frontActiveRows += 1;
    if (hasSide) sideActiveRows += 1;
    if (hasFront && hasSide) {
      matchedRows += 1;
      generatedCounts.push(Math.max(frontCount, sideCount));
    } else if (hasFront) {
      frontOnly += 1;
    } else if (hasSide) {
      sideOnly += 1;
    } else {
      emptyBoth += 1;
    }
  }

  const unionRows = matchedRows + frontOnly + sideOnly;
  return {
    activeRows: Object.freeze({ front: frontActiveRows, side: sideActiveRows, matched: matchedRows }),
    matchedRowRatio: matchedRows / Math.max(1, unionRows),
    rowMismatches: Object.freeze({ frontOnly, sideOnly, emptyBoth }),
    generatedPointsPerMatchedRow: Object.freeze(summarizeCounts(generatedCounts)),
    activePixels: Object.freeze({ front: front.activePixels, side: side.activePixels }),
  };
}

function extractRowsFromCanvas(canvas: HTMLCanvasElement, active: (r: number, g: number, b: number, a: number) => boolean): number[][] {
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) throw new Error('Cannot read 2D mask context');
  const rows = Array.from({ length: ROW_COUNT }, () => [] as number[]);
  const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
  for (let py = 0; py < canvas.height; py += SAMPLE_STRIDE) {
    const row = Math.floor((py / (canvas.height - 1)) * (ROW_COUNT - 1));
    for (let px = 0; px < canvas.width; px += SAMPLE_STRIDE) {
      const idx = (py * canvas.width + px) * 4;
      if (active(data[idx], data[idx + 1], data[idx + 2], data[idx + 3])) {
        const x = ((px / (canvas.width - 1)) - 0.5) * POINT_SCALE_X;
        rows[row].push(x);
      }
    }
  }
  return rows;
}

function rowsFromBooleanMask(activeMask: Uint8Array, width: number, height: number): number[][] {
  const rows = Array.from({ length: ROW_COUNT }, () => [] as number[]);
  for (let py = 0; py < height; py += SAMPLE_STRIDE) {
    const row = Math.floor((py / (height - 1)) * (ROW_COUNT - 1));
    for (let px = 0; px < width; px += SAMPLE_STRIDE) {
      if (activeMask[py * width + px]) {
        const x = ((px / (width - 1)) - 0.5) * POINT_SCALE_X;
        rows[row].push(x);
      }
    }
  }
  return rows;
}

function countActivePixels(rows: number[][]) {
  return rows.reduce((sum, row) => sum + row.length, 0);
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error(`Cannot load reference image: ${url}`));
    image.src = url;
  });
}

function drawFallbackTextMask(spec: MaskSpec): MaskRows {
  const canvas = document.createElement('canvas');
  canvas.width = MASK_WIDTH;
  canvas.height = MASK_HEIGHT;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) throw new Error('Cannot create 2D mask context');

  ctx.fillStyle = 'black';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = 'white';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.font = '900 104px Arial Black, Arial, sans-serif';
  ctx.fillText(spec.label, canvas.width / 2, canvas.height / 2 + 6);

  const rows = extractRowsFromCanvas(canvas, (r) => r > 128);
  return { spec, rows, rowCount: ROW_COUNT, width: canvas.width, height: canvas.height, activePixels: countActivePixels(rows) };
}

async function drawReferenceImageMask(spec: MaskSpec): Promise<MaskRows> {
  if (!spec.imageUrl) return drawFallbackTextMask(spec);
  const image = await loadImage(spec.imageUrl);
  const canvas = document.createElement('canvas');
  canvas.width = MASK_WIDTH;
  canvas.height = MASK_HEIGHT;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) throw new Error('Cannot create 2D image mask context');

  ctx.fillStyle = 'white';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  const margin = 20;
  const scale = Math.min((canvas.width - margin * 2) / image.naturalWidth, (canvas.height - margin * 2) / image.naturalHeight);
  const w = image.naturalWidth * scale;
  const h = image.naturalHeight * scale;
  ctx.drawImage(image, (canvas.width - w) / 2, (canvas.height - h) / 2, w, h);

  const rows = extractRowsFromCanvas(canvas, (r, g, b, a) => {
    if (a < 64) return false;
    const distanceFromWhite = Math.abs(255 - r) + Math.abs(255 - g) + Math.abs(255 - b);
    const saturation = Math.max(r, g, b) - Math.min(r, g, b);
    const darkInk = r + g + b < 700;
    return distanceFromWhite > 34 || saturation > 22 || darkInk;
  });

  return { spec, rows, rowCount: ROW_COUNT, width: canvas.width, height: canvas.height, activePixels: countActivePixels(rows) };
}

function rowToY(row: number) {
  return (0.5 - row / (ROW_COUNT - 1)) * POINT_SCALE_Y;
}

function generateSharedPointCloud(front: MaskRows, side: MaskRows): GeneratedCloud {
  const rand = seeded(RNG_SEED);
  const rowBalance = analyzeRowBalance(front, side);
  const positions: number[] = [];
  const colors: number[] = [];
  let rowsUsed = 0;
  let frontUsed = 0;
  let sideUsed = 0;

  const colorA = new THREE.Color('#7dd3fc');
  const colorB = new THREE.Color('#f472b6');
  const colorC = new THREE.Color('#facc15');
  const colorD = new THREE.Color('#ffffff');
  const mixed = new THREE.Color();

  for (let row = 0; row < ROW_COUNT; row += 1) {
    const xs = [...front.rows[row]];
    const zs = [...side.rows[row]];
    if (xs.length === 0 || zs.length === 0) continue;
    shuffleInPlace(xs, rand);
    shuffleInPlace(zs, rand);
    const count = Math.max(xs.length, zs.length);
    if (count <= 0) continue;
    rowsUsed += 1;
    const y = rowToY(row);
    for (let i = 0; i < count; i += 1) {
      const x = xs[i % xs.length];
      const z = -zs[i % zs.length];
      positions.push(x, y, z);
      const tint = 0.58 + 0.34 * rand();
      const xNorm = x / POINT_SCALE_X + 0.5;
      const zNorm = -z / POINT_SCALE_Z + 0.5;
      const yNorm = y / POINT_SCALE_Y + 0.5;
      mixed.copy(colorA).lerp(colorB, zNorm);
      mixed.lerp(colorC, Math.max(0, 0.35 - Math.abs(xNorm - 0.18)) * 0.75);
      mixed.lerp(colorD, Math.max(0, yNorm - 0.58) * 0.28);
      mixed.multiplyScalar(tint);
      colors.push(mixed.r, mixed.g, mixed.b);
      frontUsed += 1;
      sideUsed += 1;
    }
  }

  return {
    positions: new Float32Array(positions),
    colors: new Float32Array(colors),
    stats: {
      points: positions.length / 3,
      frontCoverage: Math.min(1, frontUsed / Math.max(1, front.activePixels)),
      sideCoverage: Math.min(1, sideUsed / Math.max(1, side.activePixels)),
      rowsUsed,
      rowCount: ROW_COUNT,
      rowBalance,
    },
  };
}

const canvas = document.querySelector<HTMLCanvasElement>('#scene')!;
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x03040a);
scene.fog = new THREE.Fog(0x03040a, 6, 13);

const frontMask = await drawReferenceImageMask(FRONT_SPEC);
const sideMask = await drawReferenceImageMask(SIDE_SPEC);
const cloud = generateSharedPointCloud(frontMask, sideMask);

const geometry = new THREE.BufferGeometry();
geometry.setAttribute('position', new THREE.BufferAttribute(cloud.positions, 3));
geometry.setAttribute('color', new THREE.BufferAttribute(cloud.colors, 3));
geometry.computeBoundingSphere();

const material = new THREE.ShaderMaterial({
  uniforms: {
    uSize: { value: POINT_SIZE * Math.min(devicePixelRatio, 2) },
    uAlpha: { value: 0.86 },
  },
  vertexShader: `
    uniform float uSize;
    varying vec3 vColor;
    void main() {
      vColor = color;
      vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
      gl_PointSize = uSize;
      gl_Position = projectionMatrix * mvPosition;
    }
  `,
  fragmentShader: `
    uniform float uAlpha;
    varying vec3 vColor;
    void main() {
      float d = length(gl_PointCoord - vec2(0.5));
      if (d > 0.5) discard;
      float alpha = smoothstep(0.5, 0.06, d) * uAlpha;
      float core = smoothstep(0.18, 0.0, d);
      vec3 glowColor = mix(vColor * 1.12, vec3(1.0), core * 0.22);
      gl_FragColor = vec4(glowColor, alpha);
    }
  `,
  vertexColors: true,
  transparent: true,
  depthWrite: false,
  blending: THREE.AdditiveBlending,
});

const pointCloud = new THREE.Points(geometry, material);
scene.add(pointCloud);

const axesGroup = new THREE.Group();
const grid = new THREE.GridHelper(4.8, 24, 0x263047, 0x101522);
grid.position.y = -0.86;
axesGroup.add(grid);
function axisLine(a: THREE.Vector3, b: THREE.Vector3, color: number) {
  return new THREE.Line(new THREE.BufferGeometry().setFromPoints([a, b]), new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.55 }));
}
axesGroup.add(
  axisLine(new THREE.Vector3(-2.1, -0.84, 0), new THREE.Vector3(2.1, -0.84, 0), 0x7dd3fc),
  axisLine(new THREE.Vector3(0, -0.84, -2.1), new THREE.Vector3(0, -0.84, 2.1), 0xfde68a),
);
scene.add(axesGroup);

function countScenePoints(root: THREE.Object3D) {
  let count = 0;
  root.traverse((object) => {
    if (object instanceof THREE.Points) count += 1;
  });
  return count;
}

function deepFreeze<T extends Record<string, unknown>>(value: T): Readonly<T> {
  Object.values(value).forEach((entry) => {
    if (entry && typeof entry === 'object') Object.freeze(entry);
  });
  return Object.freeze(value);
}

function buildLenticularQa(): LenticularQa {
  const scenePointsCount = countScenePoints(scene);
  const pointCloudUsesSharedGeometry = pointCloud.geometry === geometry;
  const attributeNames = Object.keys(geometry.attributes).sort();
  const positionAttribute = geometry.getAttribute('position');
  const colorAttribute = geometry.getAttribute('color');
  const positionCount = positionAttribute?.count ?? 0;
  const colorCount = colorAttribute?.count ?? 0;
  const positionItemSize = positionAttribute?.itemSize ?? 0;
  const colorItemSize = colorAttribute?.itemSize ?? 0;
  const pointCloudInvariantHolds = scenePointsCount === 1
    && pointCloudUsesSharedGeometry
    && attributeNames.length === 2
    && attributeNames.includes('position')
    && attributeNames.includes('color')
    && positionCount === cloud.stats.points
    && colorCount === cloud.stats.points
    && positionItemSize === 3
    && colorItemSize === 3;

  return deepFreeze({
    seed: RNG_SEED,
    maskDimensions: Object.freeze({ width: MASK_WIDTH, height: MASK_HEIGHT, sampleStride: SAMPLE_STRIDE }),
    rowCount: ROW_COUNT,
    pointCount: cloud.stats.points,
    coverage: Object.freeze({ front: cloud.stats.frontCoverage, side: cloud.stats.sideCoverage }),
    rowsUsed: cloud.stats.rowsUsed,
    rowBalance: Object.freeze(cloud.stats.rowBalance),
    projectionLabels: Object.freeze({
      front: `Front +Z orthographic projection: (x,y) => ${FRONT_SPEC.label}`,
      right: `Right +X orthographic projection: (z,y) => ${SIDE_SPEC.label}`,
    }),
    scenePointsCount,
    pointCloudUsesSharedGeometry,
    geometryAttributes: Object.freeze({
      names: Object.freeze(attributeNames),
      positionCount,
      positionItemSize,
      colorCount,
      colorItemSize,
    }),
    visualStyle: Object.freeze({
      colorSource: 'fixed-per-point-attribute',
      shaderGlowOnly: true,
      viewDependentOpacityGate: false,
      depthTestReadingGate: false,
    }),
    pointCloudInvariantHolds,
  });
}

Object.defineProperty(window, '__LENTICULAR_QA__', {
  configurable: false,
  enumerable: true,
  get: buildLenticularQa,
});

const aspect = 16 / 9;
const camera = new THREE.OrthographicCamera(-VIEW_HALF_HEIGHT * aspect, VIEW_HALF_HEIGHT * aspect, VIEW_HALF_HEIGHT, -VIEW_HALF_HEIGHT, 0.01, 100);
camera.position.set(0, 0, 6);
camera.lookAt(0, 0, 0);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.enabled = false;
controls.target.set(0, 0, 0);

const viewButtons: Record<ViewMode, HTMLButtonElement> = {
  front: document.querySelector('#frontBtn') as HTMLButtonElement,
  right: document.querySelector('#rightBtn') as HTMLButtonElement,
  back: document.querySelector('#backBtn') as HTMLButtonElement,
  left: document.querySelector('#leftBtn') as HTMLButtonElement,
  reveal: document.querySelector('#revealBtn') as HTMLButtonElement,
  orbit: document.querySelector('#orbitBtn') as HTMLButtonElement,
};
const phaseLabel = document.querySelector('#phaseLabel')!;
const phaseDetail = document.querySelector('#phaseDetail')!;
const viewBadge = document.querySelector('#viewBadge') as HTMLDivElement;
const captureStatus = document.querySelector('#captureStatus') as HTMLParagraphElement;
const recordBtn = document.querySelector('#recordBtn') as HTMLButtonElement;
const errorMetric = document.querySelector('#errorMetric')!;
const invariantQaMetric = document.querySelector('#invariantQaMetric')!;

let viewMode: ViewMode = 'front';
let playing = false;
let start = 0;
let autoTheta = 0;

const viewDefs: Record<ViewMode, { pos: THREE.Vector3; label: string; detail: string; badge: string; grid: boolean }> = {
  front: { pos: new THREE.Vector3(0, 0, 6), label: 'FRONT +Z', detail: 'same points project (x,y) to goose reference image', badge: 'GOOSE', grid: false },
  right: { pos: new THREE.Vector3(6, 0, 0), label: 'RIGHT +X', detail: 'same points project (z,y) to nubzuki reference image', badge: 'NUBZUKI', grid: false },
  back: { pos: new THREE.Vector3(0, 0, -6), label: 'BACK −Z', detail: 'same points, mirrored goose projection', badge: 'mirror: GOOSE', grid: false },
  left: { pos: new THREE.Vector3(-6, 0, 0), label: 'LEFT −X', detail: 'same points, mirrored nubzuki projection', badge: 'mirror: NUBZUKI', grid: false },
  reveal: { pos: new THREE.Vector3(4.6, 2.1, 5.1), label: '3D REVEAL', detail: 'the physical cloud is neither flat image by itself', badge: 'single 3D point cloud', grid: true },
  orbit: { pos: new THREE.Vector3(4.6, 2.1, 5.1), label: 'ORBIT', detail: 'drag to inspect the one shared point set', badge: 'free orbit', grid: true },
};

function setCameraTo(position: THREE.Vector3) {
  camera.position.copy(position);
  camera.lookAt(0, 0, 0);
  controls.target.set(0, 0, 0);
  controls.update();
}

function updateUi() {
  Object.entries(viewButtons).forEach(([mode, button]) => {
    const active = mode === viewMode;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  const def = viewDefs[viewMode];
  phaseLabel.textContent = def.label;
  phaseDetail.textContent = def.detail;
  viewBadge.textContent = def.badge;
  axesGroup.visible = def.grid;
}

function setView(mode: ViewMode) {
  viewMode = mode;
  playing = false;
  controls.enabled = mode === 'orbit';
  if (mode !== 'orbit') setCameraTo(viewDefs[mode].pos);
  updateUi();
}

Object.entries(viewButtons).forEach(([mode, button]) => {
  button.onclick = () => setView(mode as ViewMode);
});

function resize() {
  const rect = canvas.parentElement!.getBoundingClientRect();
  renderer.setSize(rect.width, rect.height, false);
  const a = rect.width / rect.height;
  camera.left = -VIEW_HALF_HEIGHT * a;
  camera.right = VIEW_HALF_HEIGHT * a;
  camera.top = VIEW_HALF_HEIGHT;
  camera.bottom = -VIEW_HALF_HEIGHT;
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
resize();

function animate(now: number) {
  requestAnimationFrame(animate);
  if (playing) {
    const t = Math.min(1, (now - start) / 10_000);
    autoTheta = t * Math.PI * 2;
    const radius = 6;
    camera.position.set(Math.sin(autoTheta) * radius, 0.35 + Math.sin(t * Math.PI) * 1.5, Math.cos(autoTheta) * radius);
    camera.lookAt(0, 0, 0);
    controls.target.set(0, 0, 0);
    const deg = ((autoTheta * 180) / Math.PI) % 360;
    phaseLabel.textContent = '10s ROTATION';
    if (deg < 45 || deg > 315) viewBadge.textContent = 'GOOSE';
    else if (deg > 45 && deg < 135) viewBadge.textContent = 'NUBZUKI';
    else if (deg > 135 && deg < 225) viewBadge.textContent = 'mirrored GOOSE';
    else viewBadge.textContent = 'mirrored NUBZUKI';
    phaseDetail.textContent = 'same cloud rotating through front/right/back/left projections';
    if (t >= 1) setView('front');
  }
  if (controls.enabled) controls.update();
  renderer.render(scene, camera);
}
requestAnimationFrame(animate);

const qa = window.__LENTICULAR_QA__;
errorMetric.textContent = `same points: ${cloud.stats.points.toLocaleString()} / matched rows: ${cloud.stats.rowsUsed}/${cloud.stats.rowCount} / active-row overlap: ${(cloud.stats.rowBalance.matchedRowRatio * 100).toFixed(1)}% / row density min-med-max: ${cloud.stats.rowBalance.generatedPointsPerMatchedRow.min}-${cloud.stats.rowBalance.generatedPointsPerMatchedRow.median}-${cloud.stats.rowBalance.generatedPointsPerMatchedRow.max} / coverage F/S: ${(cloud.stats.frontCoverage * 100).toFixed(1)}%/${(cloud.stats.sideCoverage * 100).toFixed(1)}%`;
invariantQaMetric.textContent = `Physical cloud: ${qa.scenePointsCount} THREE.Points object using 1 shared BufferGeometry (${qa.geometryAttributes.names.join(' + ')} attributes, count=${qa.pointCount.toLocaleString()}). Row QA: active rows F/S/M=${qa.rowBalance.activeRows.front}/${qa.rowBalance.activeRows.side}/${qa.rowBalance.activeRows.matched}; drops F-only/S-only/empty=${qa.rowBalance.rowMismatches.frontOnly}/${qa.rowBalance.rowMismatches.sideOnly}/${qa.rowBalance.rowMismatches.emptyBoth}; sampled active pixels F/S=${qa.rowBalance.activePixels.front.toLocaleString()}/${qa.rowBalance.activePixels.side.toLocaleString()}. Style QA: ${qa.visualStyle.colorSource}, shaderGlowOnly=${qa.visualStyle.shaderGlowOnly}, viewOpacityGate=${qa.visualStyle.viewDependentOpacityGate}, depthGate=${qa.visualStyle.depthTestReadingGate}. Helper axes/grid may have their own line geometries, but they are not point sets. Point-cloud invariant: ${qa.pointCloudInvariantHolds ? 'PASS' : 'FAIL'}.`;
setView('front');

(document.querySelector('#shotBtn') as HTMLButtonElement).onclick = () => {
  const a = document.createElement('a');
  a.download = `lenticular-${viewMode}.png`;
  a.href = renderer.domElement.toDataURL('image/png');
  a.click();
};

function getSupportedWebmMimeType() {
  const candidates = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm'];
  return candidates.find((mime) => MediaRecorder.isTypeSupported(mime)) ?? '';
}

let recording = false;
recordBtn.onclick = () => {
  if (recording) return;
  if (!('MediaRecorder' in window) || !renderer.domElement.captureStream) {
    captureStatus.textContent = 'Recording unavailable: this browser does not expose MediaRecorder/canvas captureStream.';
    return;
  }
  const mimeType = getSupportedWebmMimeType();
  const stream = renderer.domElement.captureStream(60);
  const track = stream.getVideoTracks()[0] as CanvasCaptureMediaStreamTrack | undefined;
  const chunks: Blob[] = [];
  const recorder = new MediaRecorder(stream, mimeType ? { mimeType, videoBitsPerSecond: 10_000_000 } : { videoBitsPerSecond: 10_000_000 });
  let stopTimer = 0;
  recording = true;
  recordBtn.disabled = true;
  recordBtn.classList.add('is-recording');
  recordBtn.textContent = 'Recording 10s…';
  captureStatus.textContent = 'Recording 10s rotation from the single shared point cloud.';
  recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
  recorder.onstop = () => {
    window.clearTimeout(stopTimer);
    stream.getTracks().forEach((t) => t.stop());
    recording = false;
    recordBtn.disabled = false;
    recordBtn.classList.remove('is-recording');
    recordBtn.textContent = '10초 WebM 녹화';
    playing = false;
    setView('front');
    const blob = new Blob(chunks, { type: mimeType || 'video/webm' });
    const a = document.createElement('a');
    a.download = 'lenticular-shared-cloud.webm';
    a.href = URL.createObjectURL(blob);
    a.click();
    captureStatus.textContent = `Saved lenticular-shared-cloud.webm (${(blob.size / 1024 / 1024).toFixed(2)} MB). Convert to MP4 with README ffmpeg command.`;
  };
  viewMode = 'reveal';
  controls.enabled = false;
  updateUi();
  playing = true;
  start = performance.now();
  track?.requestFrame?.();
  recorder.start(250);
  stopTimer = window.setTimeout(() => {
    track?.requestFrame?.();
    if (recorder.state !== 'inactive') recorder.stop();
  }, 10_000);
};
