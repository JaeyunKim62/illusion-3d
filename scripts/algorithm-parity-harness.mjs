import { readFile } from 'node:fs/promises';
import path from 'node:path';

const root = process.cwd();
const requireProduction = process.argv.includes('--require-production');
const failures = [];
const notes = [];

function assert(condition, message) {
  if (!condition) failures.push(message);
}

function quantileIndex(k, sourceLength, targetLength) {
  return Math.min(sourceLength - 1, Math.floor((k + 0.5) * sourceLength / targetLength));
}

function quantileMaxPair(front, side) {
  const x = [...front].sort((a, b) => a - b);
  const z = [...side].sort((a, b) => a - b);
  const n = Math.max(x.length, z.length);
  return Array.from({ length: n }, (_, k) => ({
    x: x[quantileIndex(k, x.length, n)],
    z: z[quantileIndex(k, z.length, n)],
  }));
}

function multiplicitySpread(values) {
  const counts = new Map();
  for (const value of values) counts.set(value, (counts.get(value) ?? 0) + 1);
  const used = [...counts.values()];
  return Math.max(...used) - Math.min(...used);
}

function zJumpGtRatio(pairs, threshold) {
  if (pairs.length <= 1) return 0;
  let jumps = 0;
  for (let i = 1; i < pairs.length; i += 1) {
    if (Math.abs(pairs[i].z - pairs[i - 1].z) > threshold) jumps += 1;
  }
  return jumps / (pairs.length - 1);
}

function directionFlipRatio(pairs) {
  if (pairs.length <= 2) return 0;
  let flips = 0;
  let comparisons = 0;
  let previous = 0;
  for (let i = 1; i < pairs.length; i += 1) {
    const dz = Math.sign(pairs[i].z - pairs[i - 1].z);
    if (dz === 0) continue;
    if (previous !== 0) {
      comparisons += 1;
      if (dz !== previous) flips += 1;
    }
    previous = dz;
  }
  return comparisons === 0 ? 0 : flips / comparisons;
}

function validateQuantileMath() {
  const cases = [
    { front: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], side: [0, 10, 20, 30] },
    { front: [0, 3, 5], side: [0, 1, 2, 3, 4, 5, 6] },
    { front: [0, 2, 4, 8, 16], side: [1, 9, 11, 20, 31] },
  ];

  for (const [index, testCase] of cases.entries()) {
    const pairs = quantileMaxPair(testCase.front, testCase.side);
    const usedX = new Set(pairs.map((p) => p.x));
    const usedZ = new Set(pairs.map((p) => p.z));
    assert(pairs.length === Math.max(testCase.front.length, testCase.side.length), `case ${index}: N must be max(|X|, |Z|)`);
    assert(testCase.front.every((x) => usedX.has(x)), `case ${index}: every front sample must be covered`);
    assert(testCase.side.every((z) => usedZ.has(z)), `case ${index}: every side sample must be covered`);
    assert(multiplicitySpread(pairs.map((p) => p.x)) <= 1, `case ${index}: front multiplicity spread must be <= 1`);
    assert(multiplicitySpread(pairs.map((p) => p.z)) <= 1, `case ${index}: side multiplicity spread must be <= 1`);
    assert(zJumpGtRatio(pairs, 25) <= 0.01, `case ${index}: quantile z_jump_gt25_ratio must be <= 0.01`);
    assert(directionFlipRatio(pairs) <= 0.01, `case ${index}: quantile direction_flip_ratio must be <= 0.01`);
  }
}

function cosineWeights(thetaRadians) {
  const c = Math.max(0, Math.cos(thetaRadians));
  const s = Math.max(0, Math.sin(thetaRadians));
  const denom = Math.max(1e-6, c + s);
  return { front: c / denom, side: s / denom };
}

function validateCosineS1Math() {
  const eps = 1e-9;
  const w0 = cosineWeights(0);
  const w90 = cosineWeights(Math.PI / 2);
  const w45 = cosineWeights(Math.PI / 4);
  assert(Math.abs(w0.front - 1) < eps && Math.abs(w0.side) < eps, 'cosine_s1 must preserve front endpoint color at 0 degrees');
  assert(Math.abs(w90.front) < eps && Math.abs(w90.side - 1) < eps, 'cosine_s1 must preserve side endpoint color at 90 degrees');
  assert(Math.abs(w45.front - 0.5) < eps && Math.abs(w45.side - 0.5) < eps, 'cosine_s1 must be balanced at 45 degrees');

  let maxStep = 0;
  let previous = cosineWeights(0).side;
  for (let degrees = 5; degrees <= 90; degrees += 5) {
    const current = cosineWeights((degrees * Math.PI) / 180).side;
    maxStep = Math.max(maxStep, Math.abs(current - previous));
    previous = current;
  }
  assert(maxStep <= 0.081, `cosine_s1 5-degree side-weight step too high: ${maxStep}`);
}

function sourceSlice(source, functionName) {
  const start = source.indexOf(`function ${functionName}`);
  if (start < 0) return '';
  const nextFunction = source.indexOf('\nfunction ', start + 1);
  return source.slice(start, nextFunction < 0 ? undefined : nextFunction);
}

function classifySource(source) {
  const generate = sourceSlice(source, 'generateSharedPointCloud');
  const usesShuffleInGenerate = /shuffleInPlace\(/.test(generate);
  const usesModuloInGenerate = /%\s*(frontSamples|sideSamples)\.length/.test(generate);
  const usesQuantileIndex = /quantileIndex\(/.test(generate) || /\(i \+ 0\.5\).*\.length.*count/.test(generate) || /\(k \+ 0\.5\).*\.length.*N/.test(generate);
  const sortsRows = /\.sort\(\(a, b\) => a\.coord - b\.coord\)/.test(generate) || /\.sort\(\(a, b\) => a\.coord\s*-\s*b\.coord\)/.test(generate);
  const rowPolicy = usesQuantileIndex && sortsRows && !usesShuffleInGenerate && !usesModuloInGenerate
    ? 'quantile_max'
    : usesShuffleInGenerate && usesModuloInGenerate
      ? 'shuffled_modulo_max'
      : 'unknown_or_partial';

  const hasEndpointColorAttributes = source.includes('frontColor') && source.includes('sideColor')
    && source.includes("geometry.setAttribute('frontColor'") && source.includes("geometry.setAttribute('sideColor'");
  const hasCosineBasis = /cos\(.*theta|Math\.cos|cosine_s1|uSideWeight|uFrontWeight/.test(source)
    && /sin\(.*theta|Math\.sin|uSideWeight|uFrontWeight/.test(source);
  const stillFixedColorOnly = source.includes("geometry.setAttribute('color'") && !hasEndpointColorAttributes;
  const colorPolicy = hasEndpointColorAttributes && hasCosineBasis
    ? 'cosine_s1_directional_candidate'
    : stillFixedColorOnly
      ? 'fixed_blend_or_single_color_attribute'
      : 'unknown_or_partial';

  return { rowPolicy, colorPolicy, usesShuffleInGenerate, usesModuloInGenerate, usesQuantileIndex, sortsRows, hasEndpointColorAttributes, hasCosineBasis };
}

validateQuantileMath();
validateCosineS1Math();

const sourcePath = path.join(root, 'src', 'main.ts');
const source = await readFile(sourcePath, 'utf8');
const classification = classifySource(source);

notes.push(`rowPolicy=${classification.rowPolicy}`);
notes.push(`colorPolicy=${classification.colorPolicy}`);
notes.push(`sourceFlags=${JSON.stringify({
  usesShuffleInGenerate: classification.usesShuffleInGenerate,
  usesModuloInGenerate: classification.usesModuloInGenerate,
  usesQuantileIndex: classification.usesQuantileIndex,
  sortsRows: classification.sortsRows,
  hasEndpointColorAttributes: classification.hasEndpointColorAttributes,
  hasCosineBasis: classification.hasCosineBasis,
})}`);

if (requireProduction) {
  assert(classification.rowPolicy === 'quantile_max', `production row path must be quantile_max, got ${classification.rowPolicy}`);
  assert(classification.colorPolicy === 'cosine_s1_directional_candidate', `production color path must be cosine_s1 directional candidate, got ${classification.colorPolicy}`);
}

if (failures.length) {
  console.error('Algorithm parity harness FAILED:');
  for (const failure of failures) console.error(`- ${failure}`);
  console.error('Classification notes:');
  for (const note of notes) console.error(`- ${note}`);
  process.exit(1);
}

console.log('Algorithm parity harness PASS');
console.log('- standalone quantile_max coverage/multiplicity/order checks pass');
console.log('- standalone cosine_s1 endpoint/smoothness checks pass');
for (const note of notes) console.log(`- ${note}`);
if (!requireProduction) {
  console.log('- baseline mode: source classification is reported but not enforced');
}
