import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { contestRules } from './contestRules.ts';
import './styles.css';

type ViewMode = 'front' | 'right' | 'back' | 'left' | 'reveal' | 'orbit';
type MaskSpec = { name: string; label: string; imageUrl?: string };
type Rgb = readonly [number, number, number];
type MaskSample = { coord: number; color: Rgb };
type MaskRows = { spec: MaskSpec; rows: MaskSample[][]; rowCount: number; width: number; height: number; activePixels: number };
type RowSummary = { min: number; median: number; max: number };
type RowBalanceStats = {
  activeRows: Readonly<{ front: number; side: number; matched: number }>;
  matchedRowRatio: number;
  rowMismatches: Readonly<{ frontOnly: number; sideOnly: number; emptyBoth: number }>;
  generatedPointsPerMatchedRow: Readonly<RowSummary>;
  activePixels: Readonly<{ front: number; side: number }>;
};
type CloudStats = {
  points: number;
  frontCoverage: number;
  sideCoverage: number;
  rowsUsed: number;
  rowCount: number;
  rowBalance: RowBalanceStats;
  projectionCount: 2;
  projectionOnlyPointCount: 0;
  noProjectionOnlyPoints: true;
  backgroundNoisePolicy: 'no projection-only points; every rendered point must be paired from front and side masks';
  colorPolicy: 'cosine_s1 directional color from frontColor/sideColor endpoint attributes';
  rowMaterializationPolicy: 'quantile_max';
  rowOrderPolicy: 'sorted-midpoint-quantile';
};
type LenticularQa = {
  seed: number;
  maskDimensions: Readonly<{ width: number; height: number; sampleStride: number }>;
  rowCount: number;
  pointCount: number;
  coverage: Readonly<{ front: number; side: number }>;
  rowsUsed: number;
  rowBalance: Readonly<RowBalanceStats>;
  projectionLabels: Readonly<{ front: string; right: string }>;
  projectionCount: 2;
  projectionOnlyPointCount: 0;
  noProjectionOnlyPoints: true;
  backgroundNoisePolicy: 'no projection-only points; every rendered point must be paired from front and side masks';
  scenePointsCount: number;
  pointCloudUsesSharedGeometry: boolean;
  geometryAttributes: Readonly<{
    names: readonly string[];
    positionCount: number;
    positionItemSize: number;
    frontColorCount: number;
    frontColorItemSize: number;
    sideColorCount: number;
    sideColorItemSize: number;
  }>;
  visualStyle: Readonly<{
    colorSource: 'frontColor/sideColor endpoint attributes';
    colorPolicy: 'cosine_s1-directional-color';
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
  frontColors: Float32Array;
  sideColors: Float32Array;
  stats: CloudStats;
};

const app = document.querySelector<HTMLDivElement>('#app');
if (!app) throw new Error('Missing #app root');

const MASK_WIDTH = 960;
const MASK_HEIGHT = 280;
const ROW_COUNT = 190;
const SAMPLE_STRIDE = 1;
const POINT_SCALE_X = 3.3;
const POINT_SCALE_Y = 1.2;
const POINT_SCALE_Z = 3.3;
const POINT_SIZE = 2.25;
const VIEW_HALF_HEIGHT = 1.48;
const FRONT_SPEC: MaskSpec = {
  name: 'Front +Z',
  label: 'GOOSE',
  imageUrl: '/artifacts/reference-image/goose.png',
};
const SIDE_SPEC: MaskSpec = {
  name: 'Right +X',
  label: 'NUBZUKI',
  imageUrl: '/artifacts/reference-image/cake.png',
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
      <p class="capture-status" id="captureStatus" role="status">Capture ready. Use Front/Right before PNG capture, or record the 10s +X → −Z → 45° overhead reveal path.</p>
      <section class="score-card"><h2>Invariant QA</h2><p class="qa-metric" id="invariantQaMetric">checking physical point-set invariant…</p></section>
      <section class="score-card"><h2>수학적 정의</h2><ul><li>점 하나: <code>p=(x,y,z)</code></li><li>Front +Z projection: <code>πZ(p)=(x,y)</code> → goose reference mask</li><li>Right +X projection: <code>πX(p)=(z,y)</code> → nubzuki reference mask</li><li>Back/Left는 같은 점의 좌우반전 projection</li></ul></section>
      <section class="score-card"><h2>색/빛 단계</h2><ul><li>Geometry는 그대로 하나의 <code>BufferGeometry</code>입니다.</li><li>각 점은 두 참조 이미지의 endpoint RGB(<code>frontColor</code>/<code>sideColor</code>)를 보관합니다.</li><li>shader가 카메라 각도에 따라 <code>cosine_s1</code> directional color를 계산합니다. Geometry/opacity/texture gate는 추가하지 않았습니다.</li></ul></section>
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

function isTransparentBackground(a: number) {
  return a < 64;
}

function normalizeRgb(r: number, g: number, b: number): Rgb {
  return [r / 255, g / 255, b / 255];
}

function extractColorRowsFromCanvas(canvas: HTMLCanvasElement): MaskSample[][] {
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) throw new Error('Cannot read 2D mask context');
  const rows = Array.from({ length: ROW_COUNT }, () => [] as MaskSample[]);
  const image = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const data = image.data;

  // Pairing is row-by-row: a front pixel at row N must meet a side pixel at row N.
  // Normalize each source mask's active vertical bounds into the common ROW_COUNT
  // range so tall/short reference images do not lose top/bottom rows solely due to
  // different transparent margins.
  let minActiveY = canvas.height - 1;
  let maxActiveY = 0;
  let hasActivePixel = false;
  for (let py = 0; py < canvas.height; py += SAMPLE_STRIDE) {
    for (let px = 0; px < canvas.width; px += SAMPLE_STRIDE) {
      const idx = (py * canvas.width + px) * 4;
      if (isTransparentBackground(data[idx + 3])) continue;
      minActiveY = Math.min(minActiveY, py);
      maxActiveY = Math.max(maxActiveY, py);
      hasActivePixel = true;
    }
  }
  if (!hasActivePixel) return rows;

  const activeHeight = Math.max(1, maxActiveY - minActiveY);
  for (let py = 0; py < canvas.height; py += SAMPLE_STRIDE) {
    const normalizedY = (py - minActiveY) / activeHeight;
    const row = THREE.MathUtils.clamp(Math.floor(normalizedY * (ROW_COUNT - 1)), 0, ROW_COUNT - 1);
    for (let px = 0; px < canvas.width; px += SAMPLE_STRIDE) {
      const pixelIndex = py * canvas.width + px;
      const idx = pixelIndex * 4;
      if (isTransparentBackground(data[idx + 3])) continue;
      const coord = ((px / (canvas.width - 1)) - 0.5) * POINT_SCALE_X;
      const r = data[idx];
      const g = data[idx + 1];
      const b = data[idx + 2];
      rows[row].push({ coord, color: normalizeRgb(r, g, b) });
    }
  }
  return rows;
}

function countActivePixels(rows: MaskSample[][]) {
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

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = 'white';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.font = '900 104px Arial Black, Arial, sans-serif';
  ctx.fillText(spec.label, canvas.width / 2, canvas.height / 2 + 6);

  const rows = extractColorRowsFromCanvas(canvas);
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

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const margin = 28;
  const sourceWidth = image.naturalWidth;
  const sourceHeight = image.naturalHeight;
  const scale = Math.min((canvas.width - margin * 2) / sourceWidth, (canvas.height - margin * 2) / sourceHeight);
  const w = sourceWidth * scale;
  const h = sourceHeight * scale;
  ctx.drawImage(image, 0, 0, sourceWidth, sourceHeight, (canvas.width - w) / 2, (canvas.height - h) / 2, w, h);

  const rows = extractColorRowsFromCanvas(canvas);

  return { spec, rows, rowCount: ROW_COUNT, width: canvas.width, height: canvas.height, activePixels: countActivePixels(rows) };
}

function rowToY(row: number) {
  return (0.5 - row / (ROW_COUNT - 1)) * POINT_SCALE_Y;
}

function quantileIndex(k: number, sourceLength: number, targetLength: number) {
  return Math.min(sourceLength - 1, Math.floor((k + 0.5) * sourceLength / targetLength));
}

function generateSharedPointCloud(front: MaskRows, side: MaskRows): GeneratedCloud {
  const rowBalance = analyzeRowBalance(front, side);
  const positions: number[] = [];
  const frontColors: number[] = [];
  const sideColors: number[] = [];
  let rowsUsed = 0;
  let frontUsed = 0;
  let sideUsed = 0;

  for (let row = 0; row < ROW_COUNT; row += 1) {
    const frontSamples = [...front.rows[row]].sort((a, b) => a.coord - b.coord);
    const sideSamples = [...side.rows[row]].sort((a, b) => a.coord - b.coord);
    if (frontSamples.length === 0 || sideSamples.length === 0) continue;
    const count = Math.max(frontSamples.length, sideSamples.length);
    if (count <= 0) continue;
    rowsUsed += 1;
    const y = rowToY(row);
    for (let i = 0; i < count; i += 1) {
      const frontSample = frontSamples[quantileIndex(i, frontSamples.length, count)];
      const sideSample = sideSamples[quantileIndex(i, sideSamples.length, count)];
      const x = frontSample.coord;
      const z = -sideSample.coord;
      positions.push(x, y, z);
      frontColors.push(...frontSample.color);
      sideColors.push(...sideSample.color);
      frontUsed += 1;
      sideUsed += 1;
    }
  }

  return {
    positions: new Float32Array(positions),
    frontColors: new Float32Array(frontColors),
    sideColors: new Float32Array(sideColors),
    stats: {
      points: positions.length / 3,
      frontCoverage: Math.min(1, frontUsed / Math.max(1, front.activePixels)),
      sideCoverage: Math.min(1, sideUsed / Math.max(1, side.activePixels)),
      rowsUsed,
      rowCount: ROW_COUNT,
      rowBalance,
      projectionCount: 2,
      projectionOnlyPointCount: 0,
      noProjectionOnlyPoints: true,
      backgroundNoisePolicy: 'no projection-only points; every rendered point must be paired from front and side masks',
      colorPolicy: 'cosine_s1 directional color from frontColor/sideColor endpoint attributes',
      rowMaterializationPolicy: 'quantile_max',
      rowOrderPolicy: 'sorted-midpoint-quantile',
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
geometry.setAttribute('frontColor', new THREE.BufferAttribute(cloud.frontColors, 3));
geometry.setAttribute('sideColor', new THREE.BufferAttribute(cloud.sideColors, 3));
geometry.computeBoundingSphere();

const material = new THREE.ShaderMaterial({
  uniforms: {
    uSize: { value: POINT_SIZE * Math.min(devicePixelRatio, 2) },
    uAlpha: { value: 0.78 },
    uSideWeight: { value: 0 },
  },
  vertexShader: `
    uniform float uSize;
    attribute vec3 frontColor;
    attribute vec3 sideColor;
    varying vec3 vFrontColor;
    varying vec3 vSideColor;
    void main() {
      vFrontColor = frontColor;
      vSideColor = sideColor;
      vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
      gl_PointSize = uSize;
      gl_Position = projectionMatrix * mvPosition;
    }
  `,
  fragmentShader: `
    uniform float uAlpha;
    uniform float uSideWeight;
    varying vec3 vFrontColor;
    varying vec3 vSideColor;
    void main() {
      float d = length(gl_PointCoord - vec2(0.5));
      if (d > 0.5) discard;
      float alpha = smoothstep(0.5, 0.06, d) * uAlpha;
      float core = smoothstep(0.18, 0.0, d);
      vec3 directionalColor = mix(vFrontColor, vSideColor, clamp(uSideWeight, 0.0, 1.0));
      vec3 glowColor = mix(directionalColor * 1.12, vec3(1.0), core * 0.22);
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
  const frontColorAttribute = geometry.getAttribute('frontColor');
  const sideColorAttribute = geometry.getAttribute('sideColor');
  const positionCount = positionAttribute?.count ?? 0;
  const frontColorCount = frontColorAttribute?.count ?? 0;
  const sideColorCount = sideColorAttribute?.count ?? 0;
  const positionItemSize = positionAttribute?.itemSize ?? 0;
  const frontColorItemSize = frontColorAttribute?.itemSize ?? 0;
  const sideColorItemSize = sideColorAttribute?.itemSize ?? 0;
  const pointCloudInvariantHolds = scenePointsCount === 1
    && pointCloudUsesSharedGeometry
    && attributeNames.length === 3
    && attributeNames.includes('position')
    && attributeNames.includes('frontColor')
    && attributeNames.includes('sideColor')
    && positionCount === cloud.stats.points
    && frontColorCount === cloud.stats.points
    && sideColorCount === cloud.stats.points
    && positionItemSize === 3
    && frontColorItemSize === 3
    && sideColorItemSize === 3;

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
    projectionCount: 2,
    projectionOnlyPointCount: 0,
    noProjectionOnlyPoints: true,
    backgroundNoisePolicy: 'no projection-only points; every rendered point must be paired from front and side masks',
    scenePointsCount,
    pointCloudUsesSharedGeometry,
    geometryAttributes: Object.freeze({
      names: Object.freeze(attributeNames),
      positionCount,
      positionItemSize,
      frontColorCount,
      frontColorItemSize,
      sideColorCount,
      sideColorItemSize,
    }),
    visualStyle: Object.freeze({
      colorSource: 'frontColor/sideColor endpoint attributes',
      colorPolicy: 'cosine_s1-directional-color',
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
const recordingCamera = {
  right: new THREE.Vector3(6, 0, 0),
  back: new THREE.Vector3(0, 0, -6),
  overheadReveal: new THREE.Vector3(5.45, 5.65, -5.45),
};

const viewDefs: Record<ViewMode, { pos: THREE.Vector3; label: string; detail: string; badge: string; grid: boolean }> = {
  front: { pos: new THREE.Vector3(0, 0, 6), label: 'FRONT +Z', detail: 'same points project (x,y) to goose reference image', badge: 'GOOSE', grid: false },
  right: { pos: new THREE.Vector3(6, 0, 0), label: 'RIGHT +X', detail: 'same points project (z,y) to nubzuki reference image', badge: 'NUBZUKI', grid: false },
  back: { pos: new THREE.Vector3(0, 0, -6), label: 'BACK −Z', detail: 'same points, mirrored goose projection', badge: 'mirror: GOOSE', grid: false },
  left: { pos: new THREE.Vector3(-6, 0, 0), label: 'LEFT −X', detail: 'same points, mirrored nubzuki projection', badge: 'mirror: NUBZUKI', grid: false },
  reveal: { pos: new THREE.Vector3(4.6, 2.1, 5.1), label: '3D REVEAL', detail: 'the physical cloud is neither flat image by itself', badge: 'single 3D point cloud', grid: true },
  orbit: { pos: new THREE.Vector3(4.6, 2.1, 5.1), label: 'ORBIT', detail: 'drag to inspect the one shared point set', badge: 'free orbit', grid: true },
};


function cosineS1SideWeightFromCamera() {
  const side = Math.abs(camera.position.x);
  const front = Math.abs(camera.position.z);
  const denom = Math.max(1e-6, side + front);
  return side / denom;
}

function updateDirectionalColorWeight() {
  material.uniforms.uSideWeight.value = cosineS1SideWeightFromCamera();
}

function setCameraTo(position: THREE.Vector3) {
  camera.position.copy(position);
  camera.zoom = 1;
  camera.updateProjectionMatrix();
  camera.lookAt(0, 0, 0);
  controls.target.set(0, 0, 0);
  controls.update();
  updateDirectionalColorWeight();
}

function smoothStep01(t: number) {
  const x = THREE.MathUtils.clamp(t, 0, 1);
  return x * x * (3 - 2 * x);
}

function easeInOutCubic(t: number) {
  const x = THREE.MathUtils.clamp(t, 0, 1);
  return x < 0.5 ? 4 * x * x * x : 1 - ((-2 * x + 2) ** 3) / 2;
}

function setRecordingPose(position: THREE.Vector3, zoom: number, target = new THREE.Vector3(0, 0, 0)) {
  camera.position.copy(position);
  camera.zoom = zoom;
  camera.updateProjectionMatrix();
  camera.lookAt(target);
  controls.target.copy(target);
  updateDirectionalColorWeight();
}

function updateRecordingCamera(t: number) {
  const position = new THREE.Vector3();
  const target = new THREE.Vector3(0, 0, 0);
  let zoom = 1;

  if (t < 0.18) {
    const local = smoothStep01(t / 0.18);
    position.copy(recordingCamera.right);
    zoom = THREE.MathUtils.lerp(1.0, 1.12, local);
    axesGroup.visible = false;
    viewBadge.textContent = 'NUBZUKI';
    phaseDetail.textContent = 'clean +X hold with a tiny push-in so Nubzuki reads before motion';
  } else if (t < 0.25) {
    const local = smoothStep01((t - 0.18) / 0.07);
    position.copy(recordingCamera.right);
    zoom = THREE.MathUtils.lerp(1.12, 1.04, local);
    axesGroup.visible = true;
    viewBadge.textContent = 'camera leaves +X';
    phaseDetail.textContent = 'no-cut breathing beat before the quarter-arc, keeping the Nubzuki pose locked';
  } else if (t < 0.50) {
    const local = easeInOutCubic((t - 0.25) / 0.25);
    const theta = local * Math.PI * 0.5;
    const radius = 6;
    const lift = Math.sin(local * Math.PI) * 0.86;
    position.set(Math.cos(theta) * radius, lift, -Math.sin(theta) * radius);
    zoom = THREE.MathUtils.lerp(1.04, 0.98, local);
    axesGroup.visible = true;
    viewBadge.textContent = 'NUBZUKI → GOOSE';
    phaseDetail.textContent = 'same smooth quarter-arc from +X to −Z, with x/z depth parallax exposed';
  } else if (t < 0.64) {
    const local = smoothStep01((t - 0.50) / 0.14);
    position.copy(recordingCamera.back);
    zoom = THREE.MathUtils.lerp(0.98, 1.0, local);
    axesGroup.visible = false;
    viewBadge.textContent = 'mirrored GOOSE';
    phaseDetail.textContent = 'second clean hold at −Z before the escape upward';
  } else if (t < 0.82) {
    const local = easeInOutCubic((t - 0.64) / 0.18);
    const craneReveal = new THREE.Vector3(0, 3.15, -7.15);
    position.lerpVectors(recordingCamera.back, craneReveal, local);
    zoom = THREE.MathUtils.lerp(1.0, 0.74, local);
    target.y = THREE.MathUtils.lerp(0, 0.06, local);
    axesGroup.visible = true;
    viewBadge.textContent = 'crane-out reveal';
    phaseDetail.textContent = 'pull straight upward and outward first, so the flat −Z reading breaks into depth without a camera jump';
  } else {
    const local = easeInOutCubic((t - 0.82) / 0.18);
    const craneReveal = new THREE.Vector3(0, 3.15, -7.15);
    position.lerpVectors(craneReveal, recordingCamera.overheadReveal, local);
    zoom = THREE.MathUtils.lerp(0.74, 0.54, local);
    target.y = THREE.MathUtils.lerp(0.06, 0, local);
    axesGroup.visible = true;
    viewBadge.textContent = '45° overhead reveal';
    phaseDetail.textContent = 'slow diagonal drift after the crane-out gives the widest outside view of the single 3D point cloud';
  }

  setRecordingPose(position, zoom, target);
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
    phaseLabel.textContent = '10s VIEWER PATH';
    updateRecordingCamera(t);
    if (t >= 1) setView('front');
  }
  if (controls.enabled) controls.update();
  updateDirectionalColorWeight();
  renderer.render(scene, camera);
}
requestAnimationFrame(animate);

const qa = window.__LENTICULAR_QA__;
errorMetric.textContent = `same points: ${cloud.stats.points.toLocaleString()} / matched rows: ${cloud.stats.rowsUsed}/${cloud.stats.rowCount} / active-row overlap: ${(cloud.stats.rowBalance.matchedRowRatio * 100).toFixed(1)}% / row density min-med-max: ${cloud.stats.rowBalance.generatedPointsPerMatchedRow.min}-${cloud.stats.rowBalance.generatedPointsPerMatchedRow.median}-${cloud.stats.rowBalance.generatedPointsPerMatchedRow.max} / coverage F/S: ${(cloud.stats.frontCoverage * 100).toFixed(1)}%/${(cloud.stats.sideCoverage * 100).toFixed(1)}%`;
invariantQaMetric.textContent = `Physical cloud: ${qa.scenePointsCount} THREE.Points object using 1 shared BufferGeometry (${qa.geometryAttributes.names.join(' + ')} attributes, count=${qa.pointCount.toLocaleString()}). Row QA: active rows F/S/M=${qa.rowBalance.activeRows.front}/${qa.rowBalance.activeRows.side}/${qa.rowBalance.activeRows.matched}; drops F-only/S-only/empty=${qa.rowBalance.rowMismatches.frontOnly}/${qa.rowBalance.rowMismatches.sideOnly}/${qa.rowBalance.rowMismatches.emptyBoth}; sampled active pixels F/S=${qa.rowBalance.activePixels.front.toLocaleString()}/${qa.rowBalance.activePixels.side.toLocaleString()}. Shared-space QA: projectionCount=${qa.projectionCount}, projectionOnlyPointCount=${qa.projectionOnlyPointCount}, noProjectionOnlyPoints=${qa.noProjectionOnlyPoints}; policy=${qa.backgroundNoisePolicy}; rowPolicy=${cloud.stats.rowMaterializationPolicy}/${cloud.stats.rowOrderPolicy}; colorPolicy=${qa.visualStyle.colorPolicy}. Style QA: ${qa.visualStyle.colorSource}, shaderGlowOnly=${qa.visualStyle.shaderGlowOnly}, viewOpacityGate=${qa.visualStyle.viewDependentOpacityGate}, depthGate=${qa.visualStyle.depthTestReadingGate}. Helper axes/grid may have their own line geometries, but they are not point sets. Point-cloud invariant: ${qa.pointCloudInvariantHolds ? 'PASS' : 'FAIL'}.`;
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
  captureStatus.textContent = 'Recording 10s path: +X Nubzuki hold → smooth quarter-arc to −Z mirrored goose → no-cut crane-out and 45° overhead zoom reveal.';
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
  axesGroup.visible = false;
  updateRecordingCamera(0);
  playing = true;
  start = performance.now();
  track?.requestFrame?.();
  recorder.start(250);
  stopTimer = window.setTimeout(() => {
    track?.requestFrame?.();
    if (recorder.state !== 'inactive') recorder.stop();
  }, 10_000);
};
