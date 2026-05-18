import { readFile } from 'node:fs/promises';
import path from 'node:path';

const root = process.cwd();
const sourcePath = path.join(root, 'src', 'main.ts');
const source = await readFile(sourcePath, 'utf8');
const failures = [];

function assert(condition, message) {
  if (!condition) failures.push(message);
}

const forbiddenTerms = [
  ['addTopProjectionPoints', 'projection-only top points are forbidden; every visible point must be one shared front/side point'],
  ['fallbackPoints', 'fallback projection points are forbidden because they create background noise in other views'],
  ['topProjection', 'top projection QA is forbidden until a true common-point 3-view solver exists'],
  ["'top'", 'Top view mode is disabled for the 2-view no-noise harness'],
  ['Top +Y', 'Top +Y UI is disabled for the 2-view no-noise harness'],
  ['Bottom −Y', 'Bottom view UI is disabled for the 2-view no-noise harness'],
];

for (const [term, reason] of forbiddenTerms) {
  assert(!source.includes(term), `${reason} (found ${JSON.stringify(term)})`);
}

const generateMatch = source.match(/function generateSharedPointCloud\([^)]*\): GeneratedCloud \{([\s\S]*?)\n\}/);
assert(Boolean(generateMatch), 'generateSharedPointCloud must exist with a typed GeneratedCloud return');
if (generateMatch) {
  const signature = source.match(/function generateSharedPointCloud\(([^)]*)\): GeneratedCloud/)?.[1] ?? '';
  assert(signature.includes('front: MaskRows') && signature.includes('side: MaskRows'), 'generateSharedPointCloud must take front and side masks');
  assert(!signature.includes('top'), 'generateSharedPointCloud must not take a top/projection-only mask in no-noise 2-view mode');
  assert(!generateMatch[1].includes('topMaskActive'), 'front/side point assignment must not be biased by a third mask');
  assert(!generateMatch[1].includes('addTopProjectionPoints'), 'generateSharedPointCloud must not append projection-only points after common front/side generation');
}

const qaExpectations = [
  'projectionCount: 2',
  'projectionOnlyPointCount: 0',
  'backgroundNoisePolicy',
  'noProjectionOnlyPoints',
];
for (const marker of qaExpectations) {
  assert(source.includes(marker), `QA must expose ${marker}`);
}

assert(source.includes("viewDependentOpacityGate: false"), 'view-dependent opacity gate must remain false');
assert(source.includes("depthTestReadingGate: false"), 'depth-test reading gate must remain false');

if (failures.length) {
  console.error('Shared-space/no-background-noise harness FAILED:');
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log('Shared-space/no-background-noise harness PASS');
console.log('- exactly 2 canonical readings: front(x,y) and right(z,y)');
console.log('- no projection-only top/fallback point path found');
console.log('- QA exposes projectionOnlyPointCount=0 and noProjectionOnlyPoints invariant');
