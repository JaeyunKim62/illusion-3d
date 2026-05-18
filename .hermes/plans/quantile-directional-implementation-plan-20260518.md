# Quantile Max + Directional Color Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Replace the current shuffled/modulo row pairing and fixed blended color with the verified `quantile_max` row materialization first, then a `cosine_s1` directional color material, while preserving the one-cloud invariant.

**Architecture:** Keep one physical `THREE.BufferGeometry` and one contest `THREE.Points` object. First make row pairing deterministic and testable without shader changes. Then add separate endpoint color attributes and a shader-side cosine material basis; this is view-dependent color response, not opacity/geometry gating.

**Tech Stack:** Vite, TypeScript, Three.js/WebGL, Node `.mjs` harness scripts.

---

## Pre-flight status

Current production facts from `src/main.ts`:
- `generateSharedPointCloud()` copies row samples, shuffles them, and pairs with modulo indexing.
- The generated geometry has `position` and one fixed blended `color` attribute.
- Runtime QA currently labels color as `reference-rgb-shared-blend`.

Do not skip the pre-flight commands:

```bash
npm run harness
npm run harness:algorithm
```

`npm run harness:algorithm:require-production` is expected to fail until the production code is migrated.

---

## Task 1: Install project-local algorithm guardrails

**Objective:** Keep the algorithm and agent guidance visible in-repo before production code changes.

**Files:**
- Already created: `AGENTS.md`
- Already created: `.hermes/agents/implementation-agent.md`
- Already created: `.hermes/agents/spec-review-agent.md`
- Already created: `.hermes/agents/quality-review-agent.md`
- Already created: `.hermes/agents/browser-qa-agent.md`
- Create/modify: `scripts/algorithm-parity-harness.mjs`
- Modify: `package.json`

**Steps:**
1. Add a standalone algorithm parity harness that:
   - validates `quantile_max` coverage/multiplicity/order on synthetic rows;
   - validates `cosine_s1` endpoint and smoothness math;
   - scans `src/main.ts` to classify the current production row/color path;
   - exits 0 in baseline mode but exits non-zero with `--require-production` until production code matches the target.
2. Add package scripts:
   - `harness:algorithm`
   - `harness:algorithm:require-production`
3. Run:

```bash
npm run harness:algorithm
```

Expected before implementation:
- PASS for standalone math checks.
- Source classification says production row path is still `shuffled_modulo_max` or not-yet-quantile.
- Source classification says directional color is not yet production.

---

## Task 2: Row helper extraction without behavior change

**Objective:** Prepare `src/main.ts` for a small row-pairing swap.

**Files:**
- Modify: `src/main.ts`

**Steps:**
1. Extract a helper near `generateSharedPointCloud()`:

```ts
function quantileIndex(k: number, sourceLength: number, targetLength: number) {
  return Math.min(sourceLength - 1, Math.floor((k + 0.5) * sourceLength / targetLength));
}
```

2. Do not yet change the production pairing loop.
3. Run:

```bash
npm run build
npm run harness
npm run harness:algorithm
```

Expected:
- Build/harness pass.
- Strict `require-production` may still fail.

---

## Task 3: Implement `quantile_max` row materialization

**Objective:** Replace shuffled/modulo pairing with sorted midpoint quantile pairing.

**Files:**
- Modify: `src/main.ts`
- Modify if needed: `scripts/algorithm-parity-harness.mjs`

**Implementation detail:**
Inside `generateSharedPointCloud()`:

```ts
const frontSamples = [...front.rows[row]].sort((a, b) => a.coord - b.coord);
const sideSamples = [...side.rows[row]].sort((a, b) => a.coord - b.coord);
if (frontSamples.length === 0 || sideSamples.length === 0) continue;
const count = Math.max(frontSamples.length, sideSamples.length);
...
const frontSample = frontSamples[quantileIndex(i, frontSamples.length, count)];
const sideSample = sideSamples[quantileIndex(i, sideSamples.length, count)];
```

Remove `shuffleInPlace()` from the production row materialization path. If no other code uses it, delete the helper.

**Verification:**

```bash
npm run harness
npm run harness:algorithm
npm run harness:algorithm:require-production
npm run build
```

Expected:
- Source classification reports `quantile_max` row materialization.
- No projection-only point regression.
- Build passes.
- Directional color strict gate may still be explicitly marked pending if the strict harness separates row/color checks; otherwise update the script to report row and color independently.

---

## Task 4: Add row-order QA fields

**Objective:** Make row-order improvement visible in QA instead of relying only on source scans.

**Files:**
- Modify: `src/main.ts`
- Modify: `scripts/algorithm-parity-harness.mjs`

**Add QA fields:**
- `rowMaterializationPolicy: 'quantile_max'`
- `rowOrderPolicy: 'sorted-midpoint-quantile'`
- optional row metrics if cheap:
  - `zJumpGt25Ratio`
  - `directionFlipRatioMean`

**Verification:**

```bash
npm run harness
npm run harness:algorithm:require-production
npm run build
```

Expected:
- QA text and `window.__LENTICULAR_QA__` honestly expose row policy.
- Existing invariant fields remain intact.

---

## Task 5: Prepare endpoint color attributes

**Objective:** Store both endpoint colors without changing geometry or adding a second point cloud.

**Files:**
- Modify: `src/main.ts`

**Implementation detail:**
Change `GeneratedCloud` from one `colors` attribute to two endpoint color arrays, for example:

```ts
type GeneratedCloud = {
  positions: Float32Array;
  frontColors: Float32Array;
  sideColors: Float32Array;
  stats: CloudStats;
};
```

Set geometry attributes:

```ts
geometry.setAttribute('frontColor', new THREE.BufferAttribute(cloud.frontColors, 3));
geometry.setAttribute('sideColor', new THREE.BufferAttribute(cloud.sideColors, 3));
```

Do not yet remove visual parity unless the shader is updated in the same slice. A safe transition is to keep a derived `color` attribute temporarily only if QA labels it honestly; final directional implementation should not rely on fixed blend.

**Verification:**

```bash
npm run build
npm run harness
```

Expected:
- One `THREE.Points`, one shared geometry.
- Attribute counts match point count.
- No projection-only point regression.

---

## Task 6: Implement `cosine_s1` directional color shader

**Objective:** Render endpoint colors with a cosine view-angle material basis.

**Files:**
- Modify: `src/main.ts`

**Implementation options:**
Preferred shader path:
- Vertex shader passes `frontColor` and `sideColor` varyings.
- Material has uniforms for front/right basis or a scalar `uSideWeight` updated from camera/view mode.
- For canonical front: `uSideWeight = 0`.
- For canonical right: `uSideWeight = 1`.
- For intermediate front-to-right orbit, compute equivalent cosine_s1 weight if the camera path angle is known.

Minimum acceptable first slice:

```glsl
vec3 directionalColor = mix(vFrontColor, vSideColor, uSideWeight);
```

with TypeScript computing:

```ts
const denom = Math.max(1e-6, Math.cos(theta) + Math.sin(theta));
const sideWeight = Math.sin(theta) / denom;
```

and `frontWeight = 1 - sideWeight`.

**Important:** This is allowed only as color/material response. It must not set alpha to zero, hide points, swap textures, or change geometry.

**Verification:**

```bash
npm run harness
npm run harness:algorithm
npm run harness:algorithm:require-production
npm run build
```

Expected:
- Runtime QA color policy says `cosine_s1-directional-color` or equivalent.
- `visualStyle.viewDependentOpacityGate === false`.
- Attribute QA includes endpoint color attributes.

---

## Task 7: Browser evidence and contact sheet

**Objective:** Verify actual browser/WebGL behavior, not just scripts.

**Files:**
- Create artifacts under `artifacts/evidence/` or `artifacts/algorithm-implementation/`

**Steps:**
1. Start:

```bash
npm run dev
```

2. Open browser and check:

```js
window.__LENTICULAR_QA__
```

3. Capture front/right/reveal screenshots.
4. If possible, capture 0/15/30/45/60/75/90 degree color contact sheet or metric JSON.
5. Run final:

```bash
npm run qa:submission
```

Expected:
- Browser console has no JS errors.
- One cloud invariant passes.
- Front endpoint color looks closer to front reference than fixed blend.
- Right endpoint color looks closer to side reference than fixed blend.
- Any remaining banding/speckle is reported bluntly.

---

## Final readiness gate

Do not call the implementation final until all of these are true:

```bash
npm run harness
npm run harness:algorithm:require-production
npm run build
npm run qa:submission
```

and browser QA has recorded:
- front screenshot;
- right screenshot;
- reveal screenshot;
- console error check;
- `window.__LENTICULAR_QA__` evidence.

