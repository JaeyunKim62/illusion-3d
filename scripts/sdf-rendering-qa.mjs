import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';

const root = process.cwd();
const renderingDir = path.join(root, 'SDF', 'Rendering');
const pointsPath = path.join(renderingDir, 'points.json');
const annotatedPointsPath = path.join(renderingDir, 'points-sdf.json');
const projectionMetricsPath = path.join(renderingDir, 'projection-metrics.json');
const indexPath = path.join(renderingDir, 'index.html');
const recordPath = path.join(renderingDir, 'record.html');
const ckptPath = path.join(renderingDir, 'learned_sdfs.pt');

const failures = [];
const assert = (condition, message) => {
  if (!condition) failures.push(message);
};

const [pointsRaw, annotatedRaw, projectionMetricsRaw, indexHtml, recordHtml] = await Promise.all([
  readFile(pointsPath, 'utf8'),
  readFile(annotatedPointsPath, 'utf8'),
  readFile(projectionMetricsPath, 'utf8'),
  readFile(indexPath, 'utf8'),
  readFile(recordPath, 'utf8'),
]);
const points = JSON.parse(pointsRaw);
const annotated = JSON.parse(annotatedRaw);
const projectionMetrics = JSON.parse(projectionMetricsRaw);
const ckpt = await stat(ckptPath).catch(() => undefined);

const n = Array.isArray(points.points) ? points.points.length : 0;
assert(n >= 30000, `expected at least 30000 dense neural SDF points, got ${n}`);
assert(Array.isArray(annotated.points) && annotated.points.length === n, 'points-sdf.json must preserve the dense point set');
for (const key of ['colorFront', 'colorSide', 'colorTop']) {
  assert(Array.isArray(points[key]), `missing ${key}`);
  assert(points[key]?.length === n, `${key} length must match point count`);
}
for (const key of ['front', 'side', 'top']) {
  assert(Array.isArray(annotated.sdf?.[key]), `points-sdf.json missing sdf.${key}`);
  assert(annotated.sdf?.[key]?.length === n, `sdf.${key} length must match point count`);
}
assert(Array.isArray(annotated.sdfMax) && annotated.sdfMax.length === n, 'points-sdf.json missing sdfMax');
assert(Array.isArray(annotated.sdfActiveConstraint) && annotated.sdfActiveConstraint.length === n, 'points-sdf.json missing sdfActiveConstraint');
assert(annotated.sdfAnnotation?.implicitIntersection?.includes('max('), 'points-sdf.json must document the implicit intersection');
assert(projectionMetrics.schema === 'sdf-projection-metrics/v1', 'projection-metrics.json schema mismatch');
for (const view of ['front', 'side', 'top']) {
  assert(typeof projectionMetrics.metrics?.[view]?.recall === 'number', `projection metrics missing ${view}.recall`);
  assert(typeof projectionMetrics.metrics?.[view]?.precision === 'number', `projection metrics missing ${view}.precision`);
  assert(typeof projectionMetrics.metrics?.[view]?.iou === 'number', `projection metrics missing ${view}.iou`);
  assert(typeof projectionMetrics.metrics?.[view]?.leakageRatio === 'number', `projection metrics missing ${view}.leakageRatio`);
}
assert(Boolean(ckpt?.size), 'missing learned_sdfs.pt checkpoint');

for (const [name, html] of [['index.html', indexHtml], ['record.html', recordHtml]]) {
  assert(html.includes("fetch('points-sdf.json')"), `${name} must load annotated SDF point data`);
  assert(!html.includes("fetch('../points.json')"), `${name} must not use parent points.json path`);
  assert(html.includes('__SDF_RENDERING_QA__'), `${name} must expose runtime SDF QA`);
  assert(html.includes('sdfInfo'), `${name} must bind SDF attributes into the shader`);
  assert(html.includes('uFieldReveal'), `${name} must expose the SDF field reveal uniform`);
  if (name === 'index.html') {
    assert(html.includes('referenceOverlay'), 'index.html must expose the diagnostic reference image overlay');
    assert(html.includes('diagnosticReferenceOverlay'), 'index.html QA must mark the reference overlay as diagnostic');
    assert(html.includes('setCameraForReference'), 'index.html must align the camera when a reference image is shown');
  }
  assert(html.includes('contestCloud = true'), `${name} must mark exactly one contest point cloud`);
  assert(html.includes('derivedProjectionShadow = true'), `${name} must mark the shadow as a derived rendering pass`);
  assert(!/hiddenBillboard\s*:\s*true/.test(html), `${name} must not declare hidden billboards`);
  assert(!/textureSwap\s*:\s*true/.test(html), `${name} must not declare texture swaps`);
  assert(!/geometrySwap\s*:\s*true/.test(html), `${name} must not declare geometry swaps`);
  assert(!/viewDependentOpacityGate\s*:\s*true/.test(html), `${name} must not declare opacity gates`);
}

if (failures.length) {
  console.error('SDF rendering QA FAILED:');
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log('SDF rendering QA PASS');
console.log(`- dense points: ${n.toLocaleString()}`);
console.log('- SDF annotations: front + side + top + active constraint');
console.log(
  `- projection recall F/S/T: ${projectionMetrics.metrics.front.recall.toFixed(3)} / `
  + `${projectionMetrics.metrics.side.recall.toFixed(3)} / `
  + `${projectionMetrics.metrics.top.recall.toFixed(3)}`
);
console.log('- renderer: SDF/Rendering/index.html');
console.log('- recorder: SDF/Rendering/record.html');
console.log('- runtime QA: window.__SDF_RENDERING_QA__');
