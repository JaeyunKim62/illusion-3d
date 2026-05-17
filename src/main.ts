import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import config from '../scene_config.json';
import { contestRules } from './contestRules.ts';
import './styles.css';

type Vec2 = [number, number];
type RoomKey = keyof typeof config.room.layout;
type Keyframe = { time: number; position: THREE.Vector3; target: THREE.Vector3; phase: string };
type ViewMode = 'play' | 'reference' | 'reveal' | 'orbit';
type OverlayMode = 'off' | 'ghost' | 'rays' | 'all';

const app = document.querySelector<HTMLDivElement>('#app');
if (!app) throw new Error('Missing #app root');

app.innerHTML = `
  <main class="app-shell">
    <section class="viewer-card">
      <canvas id="scene" aria-label="Perceptual Twin Room WebGL viewer"></canvas>
      <div class="hud">
        <div><b id="phaseLabel">reference camera</b><span id="phaseDetail">WHAT WE SEE alignment</span></div>
        <div class="metric" id="errorMetric">mean reprojection error: measuring…</div>
      </div>
      <div class="ending" id="endingText">WHAT WE SEE <b>≠</b> WHAT EXISTS</div>
      <div class="story-strip" aria-hidden="true">
        <span><b>1</b> align to reference view</span>
        <span><b>2</b> room reads normal</span>
        <span><b>3</b> side view reveals distortion</span>
      </div>
    </section>
    <aside class="panel">
      <p class="eyebrow">KAIST 3D Rendering Contest / Procedural WebGL</p>
      <h1>${config.projectTitle}</h1>
      <p class="lead">기준 카메라의 2D 지각 목표를 3D ray로 역투영해 만든 왜곡 방입니다. 정면에서는 <b>WHAT WE SEE</b>와 정상 방처럼 보이고, 옆으로 이동하면 실제 geometry가 드러납니다.</p>
      <div class="actions">
        <button id="playBtn" data-mode="play">10초 영상 재생</button>
        <button id="referenceBtn" data-mode="reference">기준 시점</button>
        <button id="revealBtn" data-mode="reveal">왜곡 reveal</button>
        <button id="orbitBtn" data-mode="orbit">자유 Orbit</button>
        <button id="wireBtn" data-overlay="off">Overlay: Off</button>
        <button id="shotBtn">PNG 캡처</button>
        <button id="recordBtn">10초 WebM 녹화</button>
      </div>
      <p class="hint" id="overlayHelp">Overlay groups are separated: Off → Ghost room → Rays → All. Active view buttons stay highlighted.</p>
      <p class="capture-status" id="captureStatus" role="status">Capture ready: PNG representative image or a bounded 10s WebM from timeline t=0.</p>
      <section class="score-card"><h2>구현 목표</h2><ul><li>Reference camera와 render camera 분리</li><li>back-project / project reprojection error 표시</li><li>Anamorphic text, distorted room, same-size spheres, rays/wireframe 포함</li></ul></section>
      <section class="score-card"><h2>우선 규정</h2><ul>${contestRules.map((r) => `<li><b>${r.title}</b> — ${r.implementationPolicy}</li>`).join('')}</ul></section>
    </aside>
  </main>
`;

const canvas = document.querySelector<HTMLCanvasElement>('#scene')!;
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x070b16);
scene.fog = new THREE.Fog(0x070b16, 10, 32);

const refCamera = new THREE.PerspectiveCamera(config.referenceCamera.fov, config.referenceCamera.aspect, config.referenceCamera.near, config.referenceCamera.far);
refCamera.position.fromArray(config.referenceCamera.position as [number, number, number]);
refCamera.lookAt(new THREE.Vector3().fromArray(config.referenceCamera.target as [number, number, number]));
refCamera.updateMatrixWorld(true);
refCamera.updateProjectionMatrix();

const camera = new THREE.PerspectiveCamera(50, 16 / 9, 0.1, 100);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.enabled = false;

scene.add(new THREE.HemisphereLight(0xaac7ff, 0x181b2a, 2.2));
const key = new THREE.DirectionalLight(0xffffff, 3.5);
key.position.set(4, 6, 7);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
scene.add(key);
const rim = new THREE.PointLight(0x7dd3fc, 12, 22);
rim.position.set(-4, 3, 5);
scene.add(rim);

const root = new THREE.Group();
scene.add(root);
const physicalGroup = new THREE.Group();
const overlayRoot = new THREE.Group();
const ghostOverlay = new THREE.Group();
const rayOverlay = new THREE.Group();
const frustumOverlay = new THREE.Group();
overlayRoot.add(ghostOverlay, rayOverlay, frustumOverlay);
root.add(physicalGroup, overlayRoot);

function seeded(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (1664525 * s + 1013904223) >>> 0;
    return s / 0xffffffff;
  };
}

function backprojectNDC(cam: THREE.PerspectiveCamera, u: number, v: number, depth: number) {
  cam.updateMatrixWorld(true);
  const near = new THREE.Vector3(u, v, -1).unproject(cam);
  const far = new THREE.Vector3(u, v, 1).unproject(cam);
  const dir = far.sub(near).normalize();
  return cam.position.clone().add(dir.multiplyScalar(depth));
}

function projectToNDC(cam: THREE.Camera, point: THREE.Vector3) {
  return point.clone().project(cam);
}

function pixelError(cam: THREE.Camera, point: THREE.Vector3, target: Vec2) {
  const p = projectToNDC(cam, point);
  const dx = ((p.x - target[0]) * config.render.width) / 2;
  const dy = ((p.y - target[1]) * config.render.height) / 2;
  return Math.hypot(dx, dy);
}

function screenConstantSize(depth: number, pixels: number) {
  const vh = 2 * Math.tan(THREE.MathUtils.degToRad(refCamera.fov / 2)) * depth;
  return (pixels / config.render.height) * vh;
}

function makeCheckerMaterial(a: number, b: number) {
  return new THREE.ShaderMaterial({
    uniforms: { colorA: { value: new THREE.Color(a) }, colorB: { value: new THREE.Color(b) }, scale: { value: 18 } },
    vertexShader: `varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }`,
    fragmentShader: `varying vec2 vUv; uniform vec3 colorA; uniform vec3 colorB; uniform float scale; void main(){ vec2 c=floor(vUv*scale); float m=mod(c.x+c.y,2.0); gl_FragColor=vec4(mix(colorA,colorB,m),1.0); }`,
    side: THREE.DoubleSide,
  });
}

function makeQuad(a: THREE.Vector3, b: THREE.Vector3, c: THREE.Vector3, d: THREE.Vector3, mat: THREE.Material) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute([...a.toArray(), ...b.toArray(), ...c.toArray(), ...a.toArray(), ...c.toArray(), ...d.toArray()], 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute([0, 1, 1, 1, 1, 0, 0, 1, 1, 0, 0, 0], 2));
  g.computeVertexNormals();
  const m = new THREE.Mesh(g, mat);
  m.castShadow = true;
  m.receiveShadow = true;
  return m;
}

const roomVertices = {} as Record<RoomKey, THREE.Vector3>;
(Object.keys(config.room.layout) as RoomKey[]).forEach((keyName) => {
  const [u, v] = config.room.layout[keyName] as Vec2;
  roomVertices[keyName] = backprojectNDC(refCamera, u, v, config.room.depths[keyName]);
});

const wallMat = makeCheckerMaterial(0x243b6b, 0x3559a3);
const floorMat = makeCheckerMaterial(0x172554, 0x0f766e);
const ceilMat = makeCheckerMaterial(0x1e293b, 0x334155);
const backMat = makeCheckerMaterial(0x3b0764, 0x6d28d9);
physicalGroup.add(
  makeQuad(roomVertices.outerTL, roomVertices.innerTL, roomVertices.innerBL, roomVertices.outerBL, wallMat),
  makeQuad(roomVertices.innerTR, roomVertices.outerTR, roomVertices.outerBR, roomVertices.innerBR, wallMat),
  makeQuad(roomVertices.outerTL, roomVertices.outerTR, roomVertices.innerTR, roomVertices.innerTL, ceilMat),
  makeQuad(roomVertices.innerBL, roomVertices.innerBR, roomVertices.outerBR, roomVertices.outerBL, floorMat),
  makeQuad(roomVertices.innerTL, roomVertices.innerTR, roomVertices.innerBR, roomVertices.innerBL, backMat),
);

function makeRoomEdgeLines(vertices: Record<RoomKey, THREE.Vector3>, color: number, opacity: number) {
  const pairs: [RoomKey, RoomKey][] = [
    ['outerTL', 'outerTR'], ['outerTR', 'outerBR'], ['outerBR', 'outerBL'], ['outerBL', 'outerTL'],
    ['innerTL', 'innerTR'], ['innerTR', 'innerBR'], ['innerBR', 'innerBL'], ['innerBL', 'innerTL'],
    ['outerTL', 'innerTL'], ['outerTR', 'innerTR'], ['outerBR', 'innerBR'], ['outerBL', 'innerBL'],
  ];
  const pts: number[] = [];
  pairs.forEach(([a, b]) => pts.push(...vertices[a].toArray(), ...vertices[b].toArray()));
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  return new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color, transparent: true, opacity }));
}

const physicalSilhouette = makeRoomEdgeLines(roomVertices, 0xe0f2fe, 0.34);
physicalSilhouette.name = 'Physical distorted room silhouette';
physicalGroup.add(physicalSilhouette);

const perceivedBox = new THREE.BoxGeometry(2, 1.3, 1.2);
const roomWire = new THREE.LineSegments(new THREE.EdgesGeometry(perceivedBox), new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.5 }));
roomWire.name = 'Ghost perceived rectangular room';
roomWire.position.set(0, 0, -0.4);
ghostOverlay.add(roomWire);

function makeTextMaskPoints() {
  const c = document.createElement('canvas');
  c.width = config.anamorphicText.canvasWidth;
  c.height = config.anamorphicText.canvasHeight;
  const ctx = c.getContext('2d')!;
  ctx.fillStyle = 'black';
  ctx.fillRect(0, 0, c.width, c.height);
  ctx.fillStyle = 'white';
  ctx.font = '900 116px Arial, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(config.anamorphicText.text, c.width / 2, c.height / 2 + 4);
  const data = ctx.getImageData(0, 0, c.width, c.height).data;
  const pts: Vec2[] = [];
  for (let y = 0; y < c.height; y += config.anamorphicText.sampleStride) {
    for (let x = 0; x < c.width; x += config.anamorphicText.sampleStride) {
      const pixel = (y * c.width + x) * 4;
      if (data[pixel] > 128) {
        const u = (x / c.width) * 1.55 - 0.775;
        const v = 0.56 - (y / c.height) * 0.34;
        pts.push([u, v]);
      }
    }
  }
  return pts;
}

const rand = seeded(config.anamorphicText.seed);
const textPoints = makeTextMaskPoints();
const textGeo = new THREE.PlaneGeometry(1, 1);
const textMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, emissive: 0x8bb7ff, emissiveIntensity: 0.2, roughness: 0.42, side: THREE.DoubleSide });
const pieces = new THREE.InstancedMesh(textGeo, textMat, textPoints.length);
pieces.castShadow = true;
const dummy = new THREE.Object3D();
const reprojectionErrors: number[] = [];
textPoints.forEach((ndc, i) => {
  const depth = THREE.MathUtils.lerp(config.anamorphicText.depthMin, config.anamorphicText.depthMax, rand());
  const pos = backprojectNDC(refCamera, ndc[0], ndc[1], depth);
  dummy.position.copy(pos);
  dummy.quaternion.copy(refCamera.quaternion);
  const s = screenConstantSize(depth, config.anamorphicText.piecePixelSize);
  dummy.scale.setScalar(s);
  dummy.updateMatrix();
  pieces.setMatrixAt(i, dummy.matrix);
  reprojectionErrors.push(pixelError(refCamera, pos, ndc));
});
physicalGroup.add(pieces);

const sphereMatA = new THREE.MeshStandardMaterial({ color: 0xfbbf24, roughness: 0.3, metalness: 0.15 });
const sphereMatB = new THREE.MeshStandardMaterial({ color: 0x38bdf8, roughness: 0.3, metalness: 0.15 });
const sphereA = new THREE.Mesh(new THREE.SphereGeometry(config.objects.sphereRadius, 48, 24), sphereMatA);
const sphereB = new THREE.Mesh(new THREE.SphereGeometry(config.objects.sphereRadius, 48, 24), sphereMatB);
sphereA.position.copy(backprojectNDC(refCamera, config.objects.sphereA.ndc[0], config.objects.sphereA.ndc[1], config.objects.sphereA.depth));
sphereB.position.copy(backprojectNDC(refCamera, config.objects.sphereB.ndc[0], config.objects.sphereB.ndc[1], config.objects.sphereB.depth));
sphereA.castShadow = sphereB.castShadow = true;
physicalGroup.add(sphereA, sphereB);

function makeLabelSprite(text: string, color = '#e0f2fe', accent = '#38bdf8') {
  const c = document.createElement('canvas');
  c.width = 768;
  c.height = 192;
  const ctx = c.getContext('2d')!;
  ctx.clearRect(0, 0, c.width, c.height);
  ctx.fillStyle = 'rgba(2, 6, 23, 0.76)';
  roundRect(ctx, 18, 18, c.width - 36, c.height - 36, 30);
  ctx.fill();
  ctx.strokeStyle = accent;
  ctx.lineWidth = 4;
  ctx.stroke();
  ctx.font = '900 42px Arial, sans-serif';
  ctx.fillStyle = color;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, c.width / 2, c.height / 2 + 3);
  const texture = new THREE.CanvasTexture(c);
  texture.colorSpace = THREE.SRGBColorSpace;
  const mat = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false, depthWrite: false });
  const sprite = new THREE.Sprite(mat);
  sprite.scale.set(1.55, 0.4, 1);
  sprite.renderOrder = 20;
  return sprite;
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

const physicalLabel = makeLabelSprite('Physical Twin: distorted mesh', '#f8fafc', '#fb7185');
physicalLabel.position.copy(backprojectNDC(refCamera, 0.34, -0.68, 5.2));
physicalGroup.add(physicalLabel);

const sphereLabel = makeLabelSprite('same physical size / different perceived size', '#fef3c7', '#fbbf24');
sphereLabel.position.copy(backprojectNDC(refCamera, 0.0, -0.58, 4.7));
physicalGroup.add(sphereLabel);

const perceptualLabel = makeLabelSprite('Perceptual Twin: rectangular room', '#f8fafc', '#a78bfa');
perceptualLabel.position.set(0, 1.05, -0.35);
ghostOverlay.add(perceptualLabel);

const refCameraLabel = makeLabelSprite('Reference Camera: projection constraint', '#dbeafe', '#60a5fa');
refCameraLabel.position.copy(refCamera.position).add(new THREE.Vector3(0, 0.65, -0.1));
frustumOverlay.add(refCameraLabel);

function line(points: THREE.Vector3[], color: number, opacity = 1) {
  return new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), new THREE.LineBasicMaterial({ color, transparent: opacity < 1, opacity }));
}
(Object.entries(config.room.layout) as [RoomKey, Vec2][]).forEach(([_, ndc]) => rayOverlay.add(line([refCamera.position, backprojectNDC(refCamera, ndc[0], ndc[1], 11)], 0x60a5fa, 0.3)));
textPoints.filter((_, i) => i % Math.max(1, Math.floor(textPoints.length / 8)) === 0).slice(0, 8).forEach((ndc) => rayOverlay.add(line([refCamera.position, backprojectNDC(refCamera, ndc[0], ndc[1], 7)], 0xfbbf24, 0.34)));
const helper = new THREE.CameraHelper(refCamera);
frustumOverlay.add(helper);

let viewMode: ViewMode = 'reference';
let overlayMode: OverlayMode = 'off';

const viewButtons: Record<ViewMode, HTMLButtonElement> = {
  play: document.querySelector('#playBtn') as HTMLButtonElement,
  reference: document.querySelector('#referenceBtn') as HTMLButtonElement,
  reveal: document.querySelector('#revealBtn') as HTMLButtonElement,
  orbit: document.querySelector('#orbitBtn') as HTMLButtonElement,
};
const wireBtn = document.querySelector('#wireBtn') as HTMLButtonElement;
const recordBtn = document.querySelector('#recordBtn') as HTMLButtonElement;
const captureStatus = document.querySelector('#captureStatus') as HTMLParagraphElement;
const overlayHelp = document.querySelector('#overlayHelp') as HTMLParagraphElement;

function updateUiState() {
  Object.entries(viewButtons).forEach(([mode, button]) => {
    const active = mode === viewMode;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-pressed', String(active));
  });

  const overlayLabels: Record<OverlayMode, string> = {
    off: 'Overlay: Off',
    ghost: 'Overlay: Ghost',
    rays: 'Overlay: Rays',
    all: 'Overlay: All',
  };
  wireBtn.textContent = overlayLabels[overlayMode];
  wireBtn.dataset.overlay = overlayMode;
  wireBtn.classList.toggle('is-active', overlayMode !== 'off');
  wireBtn.setAttribute('aria-pressed', String(overlayMode !== 'off'));
  overlayHelp.textContent = overlayMode === 'off'
    ? 'Overlay Off: clean judging view. Cycle overlay for ghost room, back-projection rays, and camera frustum.'
    : `Overlay ${overlayMode.toUpperCase()}: ${overlayMode === 'ghost' ? 'perceived rectangular-room wire only.' : overlayMode === 'rays' ? 'sampled projection rays only; frustum and ghost hidden.' : 'ghost room + sampled rays + reference frustum.'}`;

  ghostOverlay.visible = overlayMode === 'ghost' || overlayMode === 'all';
  rayOverlay.visible = overlayMode === 'rays' || overlayMode === 'all';
  frustumOverlay.visible = overlayMode === 'all';
  overlayRoot.visible = overlayMode !== 'off';
  physicalLabel.visible = viewMode !== 'reference';
  sphereLabel.visible = viewMode !== 'orbit';
}

function setViewMode(mode: ViewMode) {
  viewMode = mode;
  updateUiState();
}

function setOverlayMode(mode: OverlayMode) {
  overlayMode = mode;
  updateUiState();
}

const keyframes: Keyframe[] = [
  { time: 0, position: new THREE.Vector3(-2.5, 0.8, 8.5), target: new THREE.Vector3(0, 0.08, 0), phase: 'approach scattered geometry' },
  { time: 0.25, position: new THREE.Vector3(0, 0, 8), target: new THREE.Vector3(0, 0, 0), phase: 'WHAT WE SEE aligned' },
  { time: 0.45, position: new THREE.Vector3(0, 0, 8), target: new THREE.Vector3(0, 0, 0), phase: 'perceived room' },
  { time: 0.70, position: new THREE.Vector3(4, 2, 7), target: new THREE.Vector3(0, 0, 0), phase: 'physical geometry reveal' },
  { time: 0.90, position: new THREE.Vector3(6.5, 3, 9), target: new THREE.Vector3(0, 0, 0), phase: 'inverse projection overlay' },
  { time: 1, position: new THREE.Vector3(6.5, 3, 9), target: new THREE.Vector3(0, 0, 0), phase: 'WHAT EXISTS ending' },
];

function smooth(t: number) { return t * t * (3 - 2 * t); }
function lookQuaternion(pos: THREE.Vector3, target: THREE.Vector3) {
  const m = new THREE.Matrix4().lookAt(pos, target, camera.up);
  return new THREE.Quaternion().setFromRotationMatrix(m);
}
function setCameraFromTimeline(t: number) {
  const clamped = THREE.MathUtils.clamp(t, 0, 1);
  let a = keyframes[0], b = keyframes[keyframes.length - 1];
  for (let i = 0; i < keyframes.length - 1; i += 1) if (clamped >= keyframes[i].time && clamped <= keyframes[i + 1].time) { a = keyframes[i]; b = keyframes[i + 1]; break; }
  const local = smooth((clamped - a.time) / Math.max(0.0001, b.time - a.time));
  camera.position.lerpVectors(a.position, b.position, local);
  const target = new THREE.Vector3().lerpVectors(a.target, b.target, local);
  camera.quaternion.slerpQuaternions(lookQuaternion(a.position, a.target), lookQuaternion(b.position, b.target), local);
  controls.target.copy(target);
  document.querySelector('#phaseLabel')!.textContent = b.phase;
  document.querySelector('#phaseDetail')!.textContent = clamped < 0.7 ? 'reference constraints visible' : 'physical twin revealed';
  if (playing && clamped > 0.72 && overlayMode === 'off') setOverlayMode('ghost');
  document.querySelector<HTMLDivElement>('#endingText')!.classList.toggle('ending--show', clamped > 0.9);
  physicalLabel.visible = viewMode !== 'reference' && (!playing || clamped > 0.62);
  sphereLabel.visible = viewMode !== 'orbit' && (!playing || clamped < 0.72);
}

let playing = false;
let start = 0;
let lastTimeline = 0.25;
function setReference() { playing = false; controls.enabled = false; setOverlayMode('off'); setViewMode('reference'); setCameraFromTimeline(0.25); }
function setReveal() { playing = false; controls.enabled = false; setOverlayMode('ghost'); setViewMode('reveal'); setCameraFromTimeline(0.82); }

function resize() {
  const rect = canvas.parentElement!.getBoundingClientRect();
  renderer.setSize(rect.width, rect.height, false);
  camera.aspect = rect.width / rect.height;
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
resize();

function animate(now: number) {
  requestAnimationFrame(animate);
  if (playing) {
    lastTimeline = Math.min(1, (now - start) / (config.render.durationSec * 1000));
    setCameraFromTimeline(lastTimeline);
    if (lastTimeline >= 1) { playing = false; setViewMode('reveal'); }
  }
  if (controls.enabled) controls.update();
  renderer.render(scene, camera);
}
requestAnimationFrame(animate);

const meanError = reprojectionErrors.reduce((a, b) => a + b, 0) / reprojectionErrors.length;
document.querySelector('#errorMetric')!.textContent = `mean reprojection error: ${meanError.toFixed(4)} px / pieces: ${textPoints.length}`;
setReference();

viewButtons.play.onclick = () => { controls.enabled = false; setOverlayMode('off'); setViewMode('play'); playing = true; start = performance.now(); };
(document.querySelector('#referenceBtn') as HTMLButtonElement).onclick = setReference;
(document.querySelector('#revealBtn') as HTMLButtonElement).onclick = setReveal;
viewButtons.orbit.onclick = () => { playing = false; controls.enabled = true; setOverlayMode(overlayMode === 'off' ? 'all' : overlayMode); setViewMode('orbit'); controls.target.set(0, 0, 0); };
wireBtn.onclick = () => {
  const next: Record<OverlayMode, OverlayMode> = { off: 'ghost', ghost: 'rays', rays: 'all', all: 'off' };
  setOverlayMode(next[overlayMode]);
};
(document.querySelector('#shotBtn') as HTMLButtonElement).onclick = () => {
  const a = document.createElement('a');
  a.download = 'representative.png';
  a.href = renderer.domElement.toDataURL('image/png');
  a.click();
};
function getSupportedWebmMimeType() {
  const candidates = [
    'video/webm;codecs=vp9',
    'video/webm;codecs=vp8',
    'video/webm',
  ];
  return candidates.find((mime) => MediaRecorder.isTypeSupported(mime)) ?? '';
}

function startTimelineFromZeroForCapture() {
  controls.enabled = false;
  setOverlayMode('off');
  setViewMode('play');
  lastTimeline = 0;
  playing = true;
  start = performance.now();
  setCameraFromTimeline(0);
}

let recording = false;
recordBtn.onclick = () => {
  if (recording) return;
  if (!('MediaRecorder' in window) || !renderer.domElement.captureStream) {
    captureStatus.textContent = 'Recording unavailable: this browser does not expose MediaRecorder/canvas captureStream.';
    return;
  }

  const mimeType = getSupportedWebmMimeType();
  const stream = renderer.domElement.captureStream(config.render.fps);
  const track = stream.getVideoTracks()[0] as CanvasCaptureMediaStreamTrack | undefined;
  const chunks: Blob[] = [];
  const recorder = new MediaRecorder(stream, mimeType ? { mimeType, videoBitsPerSecond: 10_000_000 } : { videoBitsPerSecond: 10_000_000 });
  const durationMs = config.render.durationSec * 1000;
  let stopTimer = 0;

  recording = true;
  recordBtn.disabled = true;
  recordBtn.classList.add('is-recording');
  recordBtn.textContent = 'Recording 10s…';
  captureStatus.textContent = `Recording ${config.render.durationSec}s WebM from timeline t=0 at ${config.render.fps}fps. Do not switch tabs.`;

  recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
  recorder.onerror = () => {
    captureStatus.textContent = 'Recording error: retry in Chromium/Edge, or capture frames and convert with ffmpeg from README.';
  };
  recorder.onstop = () => {
    window.clearTimeout(stopTimer);
    stream.getTracks().forEach((t) => t.stop());
    recording = false;
    recordBtn.disabled = false;
    recordBtn.classList.remove('is-recording');
    recordBtn.textContent = '10초 WebM 녹화';
    playing = false;
    setViewMode('reveal');
    setOverlayMode('ghost');
    setCameraFromTimeline(0.82);

    const blob = new Blob(chunks, { type: mimeType || 'video/webm' });
    const a = document.createElement('a');
    a.download = 'output.webm';
    a.href = URL.createObjectURL(blob);
    a.click();
    captureStatus.textContent = `Saved output.webm (${(blob.size / 1024 / 1024).toFixed(2)} MB). Convert to MP4 with the README ffmpeg command; target <=10s and <=50MB.`;
  };

  startTimelineFromZeroForCapture();
  track?.requestFrame?.();
  recorder.start(250);
  stopTimer = window.setTimeout(() => {
    track?.requestFrame?.();
    if (recorder.state !== 'inactive') recorder.stop();
  }, durationMs);
};
