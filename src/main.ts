import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { contestRules } from './contestRules.ts';
import './styles.css';

type ViewMode = 'front' | 'frontDown' | 'right' | 'rightDown' | 'back' | 'left' | 'reveal' | 'orbit';
type MaskSpec = { name: string; label: string; imageUrl?: string };
type Rgb = readonly [number, number, number];
type MaskSample = { coord: number; color: Rgb };
type MaskRows = { spec: MaskSpec; rows: MaskSample[][]; rowCount: number; width: number; height: number; activePixels: number };
type DownSamplingStats = Readonly<{
  frontActiveIoU: number;
  sideActiveIoU: number;
  frontFallbackCount: number;
  sideFallbackCount: number;
  frontFallbackRatio: number;
  sideFallbackRatio: number;
}>;
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
  colorPolicy: 'delta_lobe_s1 directional material from four fixed endpoint/down color attributes';
  downSampling: DownSamplingStats;
  rowMaterializationPolicy: 'quantile_max';
  rowOrderPolicy: 'sorted-midpoint-quantile';
  subRowJitterPolicy: 'deterministic-low-discrepancy-y-jitter';
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
  rowMaterializationPolicy: 'quantile_max';
  rowOrderPolicy: 'sorted-midpoint-quantile';
  subRowJitterPolicy: 'deterministic-low-discrepancy-y-jitter';
  subRowJitterScale: number;
  pointSizeJitter: number;
  pointScaleY: number;
  pointSize: number;
  pointAlpha: number;
  viewHalfHeight: number;
  scenePointsCount: number;
  pointCloudUsesSharedGeometry: boolean;
  geometryAttributes: Readonly<{
    names: readonly string[];
    positionCount: number;
    positionItemSize: number;
    frontBaseColorCount: number;
    frontBaseColorItemSize: number;
    frontDownColorCount: number;
    frontDownColorItemSize: number;
    sideBaseColorCount: number;
    sideBaseColorItemSize: number;
    sideDownColorCount: number;
    sideDownColorItemSize: number;
  }>;
  visualStyle: Readonly<{
    colorSource: 'frontBaseColor/frontDownColor/sideBaseColor/sideDownColor fixed material attributes';
    colorPolicy: 'delta_lobe_s1-directional-material';
    shaderGlowOnly: boolean;
    viewDependentOpacityGate: boolean;
    depthTestReadingGate: boolean;
    textureSwap: boolean;
    geometrySwapCount: 0;
  }>;
  algorithm: 'delta_lobe_s1_directional_material';
  materialPolicy: 'fixed-position four-lobe directional color attributes';
  positionHash: string;
  positionHashStableAcrossViews: true;
  referenceImages: Readonly<{ frontBase: string; frontDown: string; sideBase: string; sideDown: string }>;
  lobe: Readonly<{
    microDeltaDegrees: number;
    sigmaDegrees: number;
    centersDegrees: Readonly<{ frontBase: number; frontDown: number; sideBase: number; sideDown: number }>;
    weightsAtCanonicalSamples: Readonly<Record<string, number>>;
    maxWrongAxisLeakageNearEndpoint: number;
  }>;
  downSampling: DownSamplingStats;
  pointCloudInvariantHolds: boolean;
};

declare global {
  interface Window {
    __LENTICULAR_QA__: LenticularQa;
  }
}

type GeneratedCloud = {
  positions: Float32Array;
  frontBaseColors: Float32Array;
  frontDownColors: Float32Array;
  sideBaseColors: Float32Array;
  sideDownColors: Float32Array;
  stats: CloudStats;
};

const app = document.querySelector<HTMLDivElement>('#app');
if (!app) throw new Error('Missing #app root');

const MASK_WIDTH = 960;
const MASK_HEIGHT = 280;
const ROW_COUNT = 190;
const SAMPLE_STRIDE = 1;
const POINT_SCALE_X = 3.3;
const POINT_SCALE_Y = 1.28;
const POINT_SCALE_Z = 3.3;
const POINT_SIZE = 2.65;
const POINT_ALPHA = 0.68;
const VIEW_HALF_HEIGHT = 1.54;
const SUB_ROW_JITTER_SCALE = 0.42;
const POINT_SIZE_JITTER = 0.10;
const FRONT_SPEC: MaskSpec = {
  name: 'Front +Z',
  label: 'NUBZUKI',
  imageUrl: '/artifacts/reference-image/nubzuki.png',
};
const SIDE_SPEC: MaskSpec = {
  name: 'Right +X',
  label: 'KUMDORI',
  imageUrl: '/artifacts/reference-image/kumdori.png',
};
const MICRO_DELTA_DEGREES = 2.0;
const SIGMA_DEGREES = 0.9;
const FRONT_DOWN_SPEC: MaskSpec = {
  name: 'Front +Z micro-angle',
  label: 'NUBZUKI-DOWN',
  imageUrl: '/artifacts/reference-image/nubzuki-down.png',
};
const SIDE_DOWN_SPEC: MaskSpec = {
  name: 'Right +X micro-angle',
  label: 'KUMDORI-DOWN',
  imageUrl: '/artifacts/reference-image/kumdori-down.png',
};
const RNG_SEED = 4792026;

app.innerHTML = `
  <main class="app-shell">
    <section class="viewer-card">
      <canvas id="scene" aria-label="Shared 3D lenticular point cloud viewer"></canvas>
      <div class="hud">
        <div><b id="phaseLabel">FRONT +Z</b><span id="phaseDetail">same points project to ${FRONT_SPEC.label} reference image</span></div>
        <div class="metric" id="errorMetric">generating shared point cloud…</div>
      </div>
      <div class="view-badge" id="viewBadge">${FRONT_SPEC.label}</div>
      <div class="story-strip" aria-hidden="true">
        <span><b>1</b> one shared BufferGeometry</span>
        <span><b>2</b> front projection: x,y → ${FRONT_SPEC.label.toLowerCase()} image</span>
        <span><b>3</b> side projection: z,y → ${SIDE_SPEC.label.toLowerCase()} image</span>
      </div>
    </section>
    <aside class="panel">
      <p class="eyebrow">KAIST 3D Rendering Contest / 3D Lenticular Point Cloud</p>
      <h1>One Cloud, Multiple Readings</h1>
      <p class="lead">이 브랜치는 글자 대신 <code>artifacts/reference-image</code>의 두 참조 이미지를 사용합니다. 두 이미지는 별도 billboard가 아니라 <b>동일한 점 하나하나</b>의 좌표 <code>(x,y,z)</code>를 공유합니다. 정면 정사영은 <code>(x,y)</code>로 <b>${FRONT_SPEC.label.toLowerCase()}</b>, 우측 정사영은 <code>(z,y)</code>로 <b>${SIDE_SPEC.label.toLowerCase()}</b> 이미지를 형성합니다.</p>
      <div class="actions">
        <button id="frontBtn" data-mode="front">Front +Z: ${FRONT_SPEC.label.toLowerCase()}</button>
        <button id="frontDownBtn" data-mode="frontDown">Front +2°: ${FRONT_DOWN_SPEC.label.toLowerCase()}</button>
        <button id="rightBtn" data-mode="right">Right +X: ${SIDE_SPEC.label.toLowerCase()}</button>
        <button id="rightDownBtn" data-mode="rightDown">Right +2°: ${SIDE_DOWN_SPEC.label.toLowerCase()}</button>
        <button id="backBtn" data-mode="back">Back −Z: mirrored A</button>
        <button id="leftBtn" data-mode="left">Left −X: mirrored B</button>
        <button id="revealBtn" data-mode="reveal">3D reveal</button>
        <button id="orbitBtn" data-mode="orbit">자유 Orbit</button>
        <button id="shotBtn">PNG 캡처</button>
        <button id="recordBtn">10초 WebM 녹화</button>
      </div>
      <p class="hint" id="overlayHelp">Orthographic canonical views only: no opacity gating, no second point set, no hidden duplicate text. Rotate/reveal to inspect the single physical point cloud.</p>
      <p class="capture-status" id="captureStatus" role="status">Capture ready. Use Front/Front+2°/Right/Right+2° before PNG capture, or record the 10s +Z white→red state, +X normal→red-accent state, then +Z overhead reveal path.</p>
      <section class="score-card"><h2>Invariant QA</h2><p class="qa-metric" id="invariantQaMetric">checking physical point-set invariant…</p></section>
      <section class="score-card"><h2>수학적 정의</h2><ul><li>점 하나: <code>p=(x,y,z)</code></li><li>Front +Z projection: <code>πZ(p)=(x,y)</code> → ${FRONT_SPEC.label.toLowerCase()} reference mask</li><li>Right +X projection: <code>πX(p)=(z,y)</code> → ${SIDE_SPEC.label.toLowerCase()} reference mask</li><li>Back/Left는 같은 점의 좌우반전 projection</li></ul></section>
      <section class="score-card"><h2>색/빛 단계</h2><ul><li>Geometry는 그대로 하나의 <code>BufferGeometry</code>입니다.</li><li>각 점은 base/down 네 참조 이미지의 고정 RGB material basis(<code>frontBaseColor</code>/<code>frontDownColor</code>/<code>sideBaseColor</code>/<code>sideDownColor</code>)를 보관합니다.</li><li>shader가 signed camera angle에 따라 <code>delta_lobe_s1</code> directional material color를 계산합니다. Geometry/opacity/texture gate는 추가하지 않았습니다.</li></ul></section>
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

function isEdgeBackgroundCandidate(r: number, g: number, b: number, a: number) {
  if (a < 64) return true;
  const luma = (r + g + b) / 3;
  const chroma = Math.max(r, g, b) - Math.min(r, g, b);
  // Some down-reference PNGs ship with a semi-transparent gray page at the
  // image edge (for example alpha≈128). Treat only low-chroma edge-connected
  // semi-transparent regions as background; enclosed opaque whites remain active.
  return a < 192 && chroma <= 32 && luma >= 72;
}

function buildEdgeBackgroundMask(canvas: HTMLCanvasElement, data: Uint8ClampedArray) {
  const width = canvas.width;
  const height = canvas.height;
  const background = new Uint8Array(width * height);
  const queue: number[] = [];
  const trySeed = (px: number, py: number) => {
    const pixelIndex = py * width + px;
    if (background[pixelIndex]) return;
    const idx = pixelIndex * 4;
    if (!isEdgeBackgroundCandidate(data[idx], data[idx + 1], data[idx + 2], data[idx + 3])) return;
    background[pixelIndex] = 1;
    queue.push(pixelIndex);
  };

  for (let x = 0; x < width; x += 1) {
    trySeed(x, 0);
    trySeed(x, height - 1);
  }
  for (let y = 1; y < height - 1; y += 1) {
    trySeed(0, y);
    trySeed(width - 1, y);
  }

  for (let head = 0; head < queue.length; head += 1) {
    const pixelIndex = queue[head];
    const x = pixelIndex % width;
    const y = Math.floor(pixelIndex / width);
    const neighbors = [pixelIndex - 1, pixelIndex + 1, pixelIndex - width, pixelIndex + width];
    for (const next of neighbors) {
      if (next < 0 || next >= background.length || background[next]) continue;
      const nx = next % width;
      const ny = Math.floor(next / width);
      if (Math.abs(nx - x) + Math.abs(ny - y) !== 1) continue;
      const idx = next * 4;
      if (!isEdgeBackgroundCandidate(data[idx], data[idx + 1], data[idx + 2], data[idx + 3])) continue;
      background[next] = 1;
      queue.push(next);
    }
  }

  return background;
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
  const edgeBackground = buildEdgeBackgroundMask(canvas, data);

  // Pairing is row-by-row: a front pixel at row N must meet a side pixel at row N.
  // Normalize each source mask's active vertical bounds into the common ROW_COUNT
  // range so tall/short reference images do not lose top/bottom rows solely due to
  // different transparent margins.
  let minActiveY = canvas.height - 1;
  let maxActiveY = 0;
  let hasActivePixel = false;
  for (let py = 0; py < canvas.height; py += SAMPLE_STRIDE) {
    for (let px = 0; px < canvas.width; px += SAMPLE_STRIDE) {
      const pixelIndex = py * canvas.width + px;
      const idx = pixelIndex * 4;
      if (edgeBackground[pixelIndex]) continue;
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
      if (edgeBackground[pixelIndex]) continue;
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
  let image: HTMLImageElement;
  try {
    image = await loadImage(spec.imageUrl);
  } catch (error) {
    console.warn(`Falling back to text mask for ${spec.label}: ${(error as Error).message}`);
    return drawFallbackTextMask(spec);
  }
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

function rowToY(row: number, jitter = 0) {
  const rowHeight = POINT_SCALE_Y / Math.max(1, ROW_COUNT - 1);
  return (0.5 - row / (ROW_COUNT - 1)) * POINT_SCALE_Y + jitter * rowHeight * SUB_ROW_JITTER_SCALE;
}

function subRowJitter(row: number, pointIndex: number) {
  const phase = (row * 0.38196601125 + pointIndex * 0.61803398875) % 1;
  return phase - 0.5;
}

function quantileIndex(k: number, sourceLength: number, targetLength: number) {
  return Math.min(sourceLength - 1, Math.floor((k + 0.5) * sourceLength / targetLength));
}

function estimateActiveIoU(base: MaskRows, down: MaskRows) {
  let intersection = 0;
  let union = 0;
  for (let row = 0; row < ROW_COUNT; row += 1) {
    const baseSet = new Set(base.rows[row].map((sample) => sample.coord.toFixed(4)));
    const downSet = new Set(down.rows[row].map((sample) => sample.coord.toFixed(4)));
    const keys = new Set([...baseSet, ...downSet]);
    union += keys.size;
    for (const key of keys) {
      if (baseSet.has(key) && downSet.has(key)) intersection += 1;
    }
  }
  return union === 0 ? 0 : intersection / union;
}

type DownColorSample = { color: Rgb; fallback: boolean };

function sampleDownColor(rowSamples: MaskSample[], coord: number): DownColorSample {
  if (rowSamples.length === 0) return { color: [0, 0, 0], fallback: true };
  let nearest = rowSamples[0];
  let nearestDistance = Math.abs(nearest.coord - coord);
  for (let i = 1; i < rowSamples.length; i += 1) {
    const candidate = rowSamples[i];
    const distance = Math.abs(candidate.coord - coord);
    if (distance < nearestDistance) {
      nearest = candidate;
      nearestDistance = distance;
    }
  }
  const sixPixelsInWorld = (6 / Math.max(1, MASK_WIDTH - 1)) * POINT_SCALE_X;
  return { color: nearest.color, fallback: nearestDistance > sixPixelsInWorld };
}

function blendRgb(a: Rgb, b: Rgb, t: number): Rgb {
  return [
    THREE.MathUtils.lerp(a[0], b[0], t),
    THREE.MathUtils.lerp(a[1], b[1], t),
    THREE.MathUtils.lerp(a[2], b[2], t),
  ];
}

function createDownSamplingStats(front: MaskRows, frontDown: MaskRows, side: MaskRows, sideDown: MaskRows, frontFallbackCount: number, sideFallbackCount: number, pointCount: number): DownSamplingStats {
  return Object.freeze({
    frontActiveIoU: estimateActiveIoU(front, frontDown),
    sideActiveIoU: estimateActiveIoU(side, sideDown),
    frontFallbackCount,
    sideFallbackCount,
    frontFallbackRatio: frontFallbackCount / Math.max(1, pointCount),
    sideFallbackRatio: sideFallbackCount / Math.max(1, pointCount),
  });
}

function generateSharedPointCloud(front: MaskRows, side: MaskRows, frontDown: MaskRows, sideDown: MaskRows): GeneratedCloud {
  const rowBalance = analyzeRowBalance(front, side);
  const positions: number[] = [];
  const frontBaseColors: number[] = [];
  const frontDownColors: number[] = [];
  const sideBaseColors: number[] = [];
  const sideDownColors: number[] = [];
  let rowsUsed = 0;
  let frontUsed = 0;
  let sideUsed = 0;
  let frontFallbackCount = 0;
  let sideFallbackCount = 0;

  for (let row = 0; row < ROW_COUNT; row += 1) {
    const frontSamples = [...front.rows[row]].sort((a, b) => a.coord - b.coord);
    const sideSamples = [...side.rows[row]].sort((a, b) => a.coord - b.coord);
    if (frontSamples.length === 0 || sideSamples.length === 0) continue;
    const count = Math.max(frontSamples.length, sideSamples.length);
    if (count <= 0) continue;
    rowsUsed += 1;
    const frontDownSamples = [...frontDown.rows[row]].sort((a, b) => a.coord - b.coord);
    const sideDownSamples = [...sideDown.rows[row]].sort((a, b) => a.coord - b.coord);
    for (let i = 0; i < count; i += 1) {
      const y = rowToY(row, subRowJitter(row, i));
      const frontSample = frontSamples[quantileIndex(i, frontSamples.length, count)];
      const sideSample = sideSamples[quantileIndex(i, sideSamples.length, count)];
      const frontDownSample = sampleDownColor(frontDownSamples, frontSample.coord);
      const sideDownSample = sampleDownColor(sideDownSamples, sideSample.coord);
      const x = frontSample.coord;
      const z = -sideSample.coord;
      positions.push(x, y, z);
      frontBaseColors.push(...frontSample.color);
      frontDownColors.push(...(frontDownSample.fallback ? blendRgb(frontSample.color, frontDownSample.color, 0.65) : frontDownSample.color));
      sideBaseColors.push(...sideSample.color);
      sideDownColors.push(...(sideDownSample.fallback ? blendRgb(sideSample.color, sideDownSample.color, 0.65) : sideDownSample.color));
      if (frontDownSample.fallback) frontFallbackCount += 1;
      if (sideDownSample.fallback) sideFallbackCount += 1;
      frontUsed += 1;
      sideUsed += 1;
    }
  }

  const pointCount = positions.length / 3;
  const downSampling = createDownSamplingStats(front, frontDown, side, sideDown, frontFallbackCount, sideFallbackCount, pointCount);
  return {
    positions: new Float32Array(positions),
    frontBaseColors: new Float32Array(frontBaseColors),
    frontDownColors: new Float32Array(frontDownColors),
    sideBaseColors: new Float32Array(sideBaseColors),
    sideDownColors: new Float32Array(sideDownColors),
    stats: {
      points: pointCount,
      frontCoverage: Math.min(1, frontUsed / Math.max(1, front.activePixels)),
      sideCoverage: Math.min(1, sideUsed / Math.max(1, side.activePixels)),
      rowsUsed,
      rowCount: ROW_COUNT,
      rowBalance,
      projectionCount: 2,
      projectionOnlyPointCount: 0,
      noProjectionOnlyPoints: true,
      backgroundNoisePolicy: 'no projection-only points; every rendered point must be paired from front and side masks',
      colorPolicy: 'delta_lobe_s1 directional material from four fixed endpoint/down color attributes',
      downSampling,
      rowMaterializationPolicy: 'quantile_max',
      rowOrderPolicy: 'sorted-midpoint-quantile',
      subRowJitterPolicy: 'deterministic-low-discrepancy-y-jitter',
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
const frontDownMask = await drawReferenceImageMask(FRONT_DOWN_SPEC);
const sideDownMask = await drawReferenceImageMask(SIDE_DOWN_SPEC);
const cloud = generateSharedPointCloud(frontMask, sideMask, frontDownMask, sideDownMask);

const geometry = new THREE.BufferGeometry();
geometry.setAttribute('position', new THREE.BufferAttribute(cloud.positions, 3));
geometry.setAttribute('frontBaseColor', new THREE.BufferAttribute(cloud.frontBaseColors, 3));
geometry.setAttribute('frontDownColor', new THREE.BufferAttribute(cloud.frontDownColors, 3));
geometry.setAttribute('sideBaseColor', new THREE.BufferAttribute(cloud.sideBaseColors, 3));
geometry.setAttribute('sideDownColor', new THREE.BufferAttribute(cloud.sideDownColors, 3));
geometry.computeBoundingSphere();

const material = new THREE.ShaderMaterial({
  uniforms: {
    uSize: { value: POINT_SIZE * Math.min(devicePixelRatio, 2) },
    uAlpha: { value: POINT_ALPHA },
    uFrontWeight: { value: 1 },
    uSideWeight: { value: 0 },
    uFrontDownWeight: { value: 0 },
    uSideDownWeight: { value: 0 },
  },
  vertexShader: `
    uniform float uSize;
    attribute vec3 frontBaseColor;
    attribute vec3 frontDownColor;
    attribute vec3 sideBaseColor;
    attribute vec3 sideDownColor;
    varying vec3 vFrontBaseColor;
    varying vec3 vFrontDownColor;
    varying vec3 vSideBaseColor;
    varying vec3 vSideDownColor;
    float hash13(vec3 p) {
      return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453123);
    }
    void main() {
      vFrontBaseColor = frontBaseColor;
      vFrontDownColor = frontDownColor;
      vSideBaseColor = sideBaseColor;
      vSideDownColor = sideDownColor;
      vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
      float sizeJitter = mix(1.0 - 0.10, 1.0 + 0.10, hash13(position));
      gl_PointSize = uSize * sizeJitter;
      gl_Position = projectionMatrix * mvPosition;
    }
  `,
  fragmentShader: `
    uniform float uAlpha;
    uniform float uFrontWeight;
    uniform float uSideWeight;
    uniform float uFrontDownWeight;
    uniform float uSideDownWeight;
    varying vec3 vFrontBaseColor;
    varying vec3 vFrontDownColor;
    varying vec3 vSideBaseColor;
    varying vec3 vSideDownColor;
    void main() {
      float d = length(gl_PointCoord - vec2(0.5));
      if (d > 0.5) discard;
      float alpha = smoothstep(0.5, 0.06, d) * uAlpha;
      float core = smoothstep(0.18, 0.0, d);
      vec3 frontLocal = mix(vFrontBaseColor, vFrontDownColor, clamp(uFrontDownWeight, 0.0, 1.0));
      vec3 sideLocal = mix(vSideBaseColor, vSideDownColor, clamp(uSideDownWeight, 0.0, 1.0));
      vec3 directionalColor = (frontLocal * uFrontWeight) + (sideLocal * uSideWeight);
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

function hashPositions(positions: Float32Array) {
  let hash = 2166136261;
  for (let i = 0; i < positions.length; i += 1) {
    const quantized = Math.round((positions[i] + 8) * 10000);
    hash ^= quantized & 0xff;
    hash = Math.imul(hash, 16777619);
    hash ^= (quantized >>> 8) & 0xff;
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, '0');
}

function gaussianLobe(angle: number, center: number, sigma: number) {
  const d = (angle - center) / sigma;
  return Math.exp(-0.5 * d * d);
}

function normalizedDownLobe(angle: number, baseCenter: number, downCenter: number) {
  const base = gaussianLobe(angle, baseCenter, SIGMA_DEGREES);
  const down = gaussianLobe(angle, downCenter, SIGMA_DEGREES);
  return down / Math.max(1e-6, base + down);
}

function canonicalLobeWeights() {
  return Object.freeze({
    front0: normalizedDownLobe(0, 0, MICRO_DELTA_DEGREES),
    frontDown: normalizedDownLobe(MICRO_DELTA_DEGREES, 0, MICRO_DELTA_DEGREES),
    side90: normalizedDownLobe(90, 90, 90 + MICRO_DELTA_DEGREES),
    sideDown: normalizedDownLobe(90 + MICRO_DELTA_DEGREES, 90, 90 + MICRO_DELTA_DEGREES),
  });
}

function cosineS1SideWeightFromPosition(position: THREE.Vector3) {
  const side = Math.abs(position.x);
  const front = Math.abs(position.z);
  const denom = Math.max(1e-6, side + front);
  return side / denom;
}

function buildLenticularQa(): LenticularQa {
  const scenePointsCount = countScenePoints(scene);
  const pointCloudUsesSharedGeometry = pointCloud.geometry === geometry;
  const attributeNames = Object.keys(geometry.attributes).sort();
  const positionAttribute = geometry.getAttribute('position');
  const frontBaseColorAttribute = geometry.getAttribute('frontBaseColor');
  const frontDownColorAttribute = geometry.getAttribute('frontDownColor');
  const sideBaseColorAttribute = geometry.getAttribute('sideBaseColor');
  const sideDownColorAttribute = geometry.getAttribute('sideDownColor');
  const positionCount = positionAttribute?.count ?? 0;
  const frontBaseColorCount = frontBaseColorAttribute?.count ?? 0;
  const frontDownColorCount = frontDownColorAttribute?.count ?? 0;
  const sideBaseColorCount = sideBaseColorAttribute?.count ?? 0;
  const sideDownColorCount = sideDownColorAttribute?.count ?? 0;
  const positionItemSize = positionAttribute?.itemSize ?? 0;
  const frontBaseColorItemSize = frontBaseColorAttribute?.itemSize ?? 0;
  const frontDownColorItemSize = frontDownColorAttribute?.itemSize ?? 0;
  const sideBaseColorItemSize = sideBaseColorAttribute?.itemSize ?? 0;
  const sideDownColorItemSize = sideDownColorAttribute?.itemSize ?? 0;
  const pointCloudInvariantHolds = scenePointsCount === 1
    && pointCloudUsesSharedGeometry
    && attributeNames.length === 5
    && attributeNames.includes('position')
    && attributeNames.includes('frontBaseColor')
    && attributeNames.includes('frontDownColor')
    && attributeNames.includes('sideBaseColor')
    && attributeNames.includes('sideDownColor')
    && positionCount === cloud.stats.points
    && frontBaseColorCount === cloud.stats.points
    && frontDownColorCount === cloud.stats.points
    && sideBaseColorCount === cloud.stats.points
    && sideDownColorCount === cloud.stats.points
    && positionItemSize === 3
    && frontBaseColorItemSize === 3
    && frontDownColorItemSize === 3
    && sideBaseColorItemSize === 3
    && sideDownColorItemSize === 3;

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
    rowMaterializationPolicy: cloud.stats.rowMaterializationPolicy,
    rowOrderPolicy: cloud.stats.rowOrderPolicy,
    subRowJitterPolicy: cloud.stats.subRowJitterPolicy,
    subRowJitterScale: SUB_ROW_JITTER_SCALE,
    pointSizeJitter: POINT_SIZE_JITTER,
    pointScaleY: POINT_SCALE_Y,
    pointSize: POINT_SIZE,
    pointAlpha: POINT_ALPHA,
    viewHalfHeight: VIEW_HALF_HEIGHT,
    scenePointsCount,
    pointCloudUsesSharedGeometry,
    geometryAttributes: Object.freeze({
      names: Object.freeze(attributeNames),
      positionCount,
      positionItemSize,
      frontBaseColorCount,
      frontBaseColorItemSize,
      frontDownColorCount,
      frontDownColorItemSize,
      sideBaseColorCount,
      sideBaseColorItemSize,
      sideDownColorCount,
      sideDownColorItemSize,
    }),
    visualStyle: Object.freeze({
      colorSource: 'frontBaseColor/frontDownColor/sideBaseColor/sideDownColor fixed material attributes',
      colorPolicy: 'delta_lobe_s1-directional-material',
      shaderGlowOnly: true,
      viewDependentOpacityGate: false,
      depthTestReadingGate: false,
      textureSwap: false,
      geometrySwapCount: 0,
    }),
    algorithm: 'delta_lobe_s1_directional_material',
    materialPolicy: 'fixed-position four-lobe directional color attributes',
    positionHash: hashPositions(cloud.positions),
    positionHashStableAcrossViews: true,
    referenceImages: Object.freeze({
      frontBase: FRONT_SPEC.imageUrl ?? FRONT_SPEC.label,
      frontDown: FRONT_DOWN_SPEC.imageUrl ?? FRONT_DOWN_SPEC.label,
      sideBase: SIDE_SPEC.imageUrl ?? SIDE_SPEC.label,
      sideDown: SIDE_DOWN_SPEC.imageUrl ?? SIDE_DOWN_SPEC.label,
    }),
    lobe: Object.freeze({
      microDeltaDegrees: MICRO_DELTA_DEGREES,
      sigmaDegrees: SIGMA_DEGREES,
      centersDegrees: Object.freeze({ frontBase: 0, frontDown: MICRO_DELTA_DEGREES, sideBase: 90, sideDown: 90 + MICRO_DELTA_DEGREES }),
      weightsAtCanonicalSamples: canonicalLobeWeights(),
      maxWrongAxisLeakageNearEndpoint: Math.max(cosineS1SideWeightFromPosition(new THREE.Vector3(Math.sin(THREE.MathUtils.degToRad(MICRO_DELTA_DEGREES)) * 6, 0, Math.cos(THREE.MathUtils.degToRad(MICRO_DELTA_DEGREES)) * 6)), 1 - cosineS1SideWeightFromPosition(new THREE.Vector3(Math.cos(THREE.MathUtils.degToRad(MICRO_DELTA_DEGREES)) * 6, 0, Math.sin(THREE.MathUtils.degToRad(MICRO_DELTA_DEGREES)) * 6))),
    }),
    downSampling: cloud.stats.downSampling,
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
  frontDown: document.querySelector('#frontDownBtn') as HTMLButtonElement,
  right: document.querySelector('#rightBtn') as HTMLButtonElement,
  rightDown: document.querySelector('#rightDownBtn') as HTMLButtonElement,
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
  front: new THREE.Vector3(0, 0, 6),
  frontDown: new THREE.Vector3(Math.sin(THREE.MathUtils.degToRad(MICRO_DELTA_DEGREES)) * 6, 0, Math.cos(THREE.MathUtils.degToRad(MICRO_DELTA_DEGREES)) * 6),
  right: new THREE.Vector3(6, 0, 0),
  rightDown: new THREE.Vector3(Math.cos(THREE.MathUtils.degToRad(MICRO_DELTA_DEGREES)) * 6, 0, -Math.sin(THREE.MathUtils.degToRad(MICRO_DELTA_DEGREES)) * 6),
  overheadReveal: new THREE.Vector3(5.45, 5.65, 5.45),
};

const viewDefs: Record<ViewMode, { pos: THREE.Vector3; label: string; detail: string; badge: string; grid: boolean }> = {
  front: { pos: new THREE.Vector3(0, 0, 6), label: 'FRONT +Z', detail: `base lobe: same points project (x,y) to ${FRONT_SPEC.label.toLowerCase()} reference image`, badge: FRONT_SPEC.label, grid: false },
  frontDown: { pos: new THREE.Vector3(Math.sin(THREE.MathUtils.degToRad(MICRO_DELTA_DEGREES)) * 6, 0, Math.cos(THREE.MathUtils.degToRad(MICRO_DELTA_DEGREES)) * 6), label: 'FRONT +Z MICRO +2°', detail: `micro-angle material lobe: same fixed points switch color basis toward ${FRONT_DOWN_SPEC.label.toLowerCase()}`, badge: FRONT_DOWN_SPEC.label, grid: false },
  right: { pos: new THREE.Vector3(6, 0, 0), label: 'RIGHT +X', detail: `base lobe: same points project (z,y) to ${SIDE_SPEC.label.toLowerCase()} reference image`, badge: SIDE_SPEC.label, grid: false },
  rightDown: { pos: new THREE.Vector3(Math.cos(THREE.MathUtils.degToRad(MICRO_DELTA_DEGREES)) * 6, 0, -Math.sin(THREE.MathUtils.degToRad(MICRO_DELTA_DEGREES)) * 6), label: 'RIGHT +X MICRO +2°', detail: `micro-angle material lobe: same fixed points switch color basis toward ${SIDE_DOWN_SPEC.label.toLowerCase()}`, badge: SIDE_DOWN_SPEC.label, grid: false },
  back: { pos: new THREE.Vector3(0, 0, -6), label: 'BACK −Z', detail: `same points, mirrored ${FRONT_SPEC.label.toLowerCase()} projection`, badge: `mirror: ${FRONT_SPEC.label}`, grid: false },
  left: { pos: new THREE.Vector3(-6, 0, 0), label: 'LEFT −X', detail: `same points, mirrored ${SIDE_SPEC.label.toLowerCase()} projection`, badge: `mirror: ${SIDE_SPEC.label}`, grid: false },
  reveal: { pos: new THREE.Vector3(4.6, 2.1, 5.1), label: '3D REVEAL', detail: 'the physical cloud is neither flat image by itself', badge: 'single 3D point cloud', grid: true },
  orbit: { pos: new THREE.Vector3(4.6, 2.1, 5.1), label: 'ORBIT', detail: 'drag to inspect the one shared point set and its fixed-position directional material lobes', badge: 'free orbit', grid: true },
};


function signedAzimuthDegreesFromCamera() {
  return THREE.MathUtils.radToDeg(Math.atan2(camera.position.x, camera.position.z));
}

function cosineS1SideWeightFromCamera() {
  return cosineS1SideWeightFromPosition(camera.position);
}

function updateDirectionalColorWeight() {
  const sideWeight = cosineS1SideWeightFromCamera();
  const frontWeight = 1 - sideWeight;
  const azimuth = signedAzimuthDegreesFromCamera();
  material.uniforms.uFrontWeight.value = frontWeight;
  material.uniforms.uSideWeight.value = sideWeight;
  material.uniforms.uFrontDownWeight.value = normalizedDownLobe(azimuth, 0, MICRO_DELTA_DEGREES);
  material.uniforms.uSideDownWeight.value = normalizedDownLobe(azimuth, 90, 90 + MICRO_DELTA_DEGREES);
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

  if (t < 0.13) {
    const local = smoothStep01(t / 0.13);
    position.copy(recordingCamera.front);
    zoom = THREE.MathUtils.lerp(1.0, 1.10, local);
    axesGroup.visible = false;
    viewBadge.textContent = `${FRONT_SPEC.label}: white heart/KAIST`;
    phaseDetail.textContent = `clean +Z hold: ${FRONT_SPEC.label.toLowerCase()} base state with white heart and white KAIST`;
  } else if (t < 0.24) {
    const local = smoothStep01((t - 0.13) / 0.11);
    position.lerpVectors(recordingCamera.front, recordingCamera.frontDown, local);
    zoom = THREE.MathUtils.lerp(1.10, 1.14, local);
    axesGroup.visible = false;
    viewBadge.textContent = `${FRONT_DOWN_SPEC.label}: red heart/KAIST`;
    phaseDetail.textContent = 'front micro-angle lobe: same +Z point cloud switches heart and KAIST material from white to red';
  } else if (t < 0.32) {
    const local = smoothStep01((t - 0.24) / 0.08);
    position.copy(recordingCamera.frontDown);
    zoom = THREE.MathUtils.lerp(1.14, 1.06, local);
    axesGroup.visible = false;
    viewBadge.textContent = `${FRONT_DOWN_SPEC.label}: red hold`;
    phaseDetail.textContent = 'short Nubzuki red-state hold; no geometry or opacity change';
  } else if (t < 0.53) {
    const local = easeInOutCubic((t - 0.32) / 0.21);
    const theta = THREE.MathUtils.lerp(THREE.MathUtils.degToRad(MICRO_DELTA_DEGREES), Math.PI * 0.5, local);
    const radius = 6;
    const lift = Math.sin(local * Math.PI) * 0.86;
    position.set(Math.sin(theta) * radius, lift, Math.cos(theta) * radius);
    zoom = THREE.MathUtils.lerp(1.06, 0.98, local);
    axesGroup.visible = true;
    viewBadge.textContent = `${FRONT_SPEC.label} → ${SIDE_SPEC.label}`;
    phaseDetail.textContent = 'smooth +Z to +X quarter-arc, keeping the viewer path on the positive-Z side';
  } else if (t < 0.62) {
    const local = smoothStep01((t - 0.53) / 0.09);
    position.copy(recordingCamera.right);
    zoom = THREE.MathUtils.lerp(0.98, 1.08, local);
    axesGroup.visible = false;
    viewBadge.textContent = `${SIDE_SPEC.label}: normal`;
    phaseDetail.textContent = `clean +X hold: ${SIDE_SPEC.label.toLowerCase()} base state before antenna/cheek red accents`;
  } else if (t < 0.72) {
    const local = smoothStep01((t - 0.62) / 0.10);
    position.lerpVectors(recordingCamera.right, recordingCamera.rightDown, local);
    zoom = THREE.MathUtils.lerp(1.08, 1.12, local);
    axesGroup.visible = false;
    viewBadge.textContent = `${SIDE_DOWN_SPEC.label}: red accents`;
    phaseDetail.textContent = 'right micro-angle lobe: same +X point cloud switches Kumdori antenna tip and cheeks toward red accents';
  } else if (t < 0.80) {
    const local = smoothStep01((t - 0.72) / 0.08);
    position.copy(recordingCamera.rightDown);
    zoom = THREE.MathUtils.lerp(1.12, 1.02, local);
    axesGroup.visible = false;
    viewBadge.textContent = `${SIDE_DOWN_SPEC.label}: red hold`;
    phaseDetail.textContent = 'short Kumdori red-accent hold before the final single-cloud reveal';
  } else if (t < 0.90) {
    const local = easeInOutCubic((t - 0.80) / 0.10);
    const craneReveal = new THREE.Vector3(2.25, 3.1, 6.65);
    position.lerpVectors(recordingCamera.rightDown, craneReveal, local);
    zoom = THREE.MathUtils.lerp(1.02, 0.74, local);
    target.y = THREE.MathUtils.lerp(0, 0.06, local);
    axesGroup.visible = true;
    viewBadge.textContent = '+Z crane-out reveal';
    phaseDetail.textContent = 'pull upward and outward from the positive-Z side for the final single-cloud depth reveal';
  } else {
    const local = easeInOutCubic((t - 0.90) / 0.10);
    const craneReveal = new THREE.Vector3(2.25, 3.1, 6.65);
    position.lerpVectors(craneReveal, recordingCamera.overheadReveal, local);
    zoom = THREE.MathUtils.lerp(0.74, 0.54, local);
    target.y = THREE.MathUtils.lerp(0.06, 0, local);
    axesGroup.visible = true;
    viewBadge.textContent = '+Z 45° overhead reveal';
    phaseDetail.textContent = 'final diagonal drift stays in positive Z while exposing the single 3D point cloud structure';
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
invariantQaMetric.textContent = `Physical cloud: ${qa.scenePointsCount} THREE.Points object using 1 shared BufferGeometry (${qa.geometryAttributes.names.join(' + ')} attributes, count=${qa.pointCount.toLocaleString()}). Row QA: active rows F/S/M=${qa.rowBalance.activeRows.front}/${qa.rowBalance.activeRows.side}/${qa.rowBalance.activeRows.matched}; drops F-only/S-only/empty=${qa.rowBalance.rowMismatches.frontOnly}/${qa.rowBalance.rowMismatches.sideOnly}/${qa.rowBalance.rowMismatches.emptyBoth}; sampled active pixels F/S=${qa.rowBalance.activePixels.front.toLocaleString()}/${qa.rowBalance.activePixels.side.toLocaleString()}. Shared-space QA: projectionCount=${qa.projectionCount}, projectionOnlyPointCount=${qa.projectionOnlyPointCount}, noProjectionOnlyPoints=${qa.noProjectionOnlyPoints}; policy=${qa.backgroundNoisePolicy}; rowPolicy=${cloud.stats.rowMaterializationPolicy}/${cloud.stats.rowOrderPolicy}; yJitter=${cloud.stats.subRowJitterPolicy}@${SUB_ROW_JITTER_SCALE}; sizeJitter=±${POINT_SIZE_JITTER}; pointScaleY=${POINT_SCALE_Y}; pointSize=${POINT_SIZE}; alpha=${POINT_ALPHA}; algorithm=${qa.algorithm}; colorPolicy=${qa.visualStyle.colorPolicy}; lobe Δ=${qa.lobe.microDeltaDegrees}° σ=${qa.lobe.sigmaDegrees}°; down IoU F/S=${qa.downSampling.frontActiveIoU.toFixed(3)}/${qa.downSampling.sideActiveIoU.toFixed(3)}; down fallback F/S=${(qa.downSampling.frontFallbackRatio * 100).toFixed(1)}%/${(qa.downSampling.sideFallbackRatio * 100).toFixed(1)}%. Style QA: ${qa.visualStyle.colorSource}, shaderGlowOnly=${qa.visualStyle.shaderGlowOnly}, textureSwap=${qa.visualStyle.textureSwap}, viewOpacityGate=${qa.visualStyle.viewDependentOpacityGate}, depthGate=${qa.visualStyle.depthTestReadingGate}, geometrySwapCount=${qa.visualStyle.geometrySwapCount}. Helper axes/grid may have their own line geometries, but they are not point sets. Point-cloud invariant: ${qa.pointCloudInvariantHolds ? 'PASS' : 'FAIL'}.`;
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
  captureStatus.textContent = 'Recording 10s path: +Z white→red heart/KAIST → +X normal→red antenna/cheeks → positive-Z overhead reveal.';
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
