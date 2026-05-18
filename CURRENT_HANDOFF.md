# Current handoff — 2-view goose / nubzuki lenticular point cloud

Date: 2026-05-18
Branch: `reference-image-two-view`
Latest important commit: `e94de25 test: enforce shared 2-view point space`

## Current direction

The project is now a KAIST 3D Rendering Contest browser/WebGL artifact based on one shared 3D point cloud.

The artifact should be judged and developed as:

```text
One physical point set P, multiple orthographic readings.
For each point p=(x,y,z):
  Front +Z view uses (x,y) and should read as goose.
  Right +X view uses (z,y) and should read as nubzuki.
```

This is the authoritative direction. Older `Perceptual Twin Room` and failed 3-view/top-projection materials are historical only.

## Non-negotiable invariant

Keep exactly one physical point cloud for the readings.

Allowed:

- one `THREE.Points` object for the contest object,
- one shared `THREE.BufferGeometry`,
- fixed per-point `position`, `frontColor`, and `sideColor` attributes,
- shader glow / splat styling,
- helper axes/grid/labels as non-reading diagnostics,
- front/right/back/left/reveal/orbit camera modes.

Forbidden:

- second point cloud for the second image,
- hidden image/text billboards,
- view-dependent opacity gates,
- depth-test reading gates,
- top/third-view projection-only points,
- fallback points that exist only to satisfy one view.

Reason: the failed 3-view attempt added top projection-only points, which appeared as barcode-like background noise in front/right views. The current harness prevents that regression.

## Harness / verification

Main check:

```bash
npm run harness
```

This runs:

```bash
node scripts/shared-space-harness.mjs && npm run build
```

The harness verifies:

- no `addTopProjectionPoints`,
- no `fallbackPoints`,
- no `topProjection`,
- no `Top +Y` / `Bottom -Y` UI,
- `generateSharedPointCloud()` only takes front and side masks,
- QA exposes `projectionOnlyPointCount: 0`,
- QA exposes `noProjectionOnlyPoints`,
- `viewDependentOpacityGate: false`,
- `depthTestReadingGate: false`.

Final package sanity check:

```bash
npm run qa:submission
```

Latest verified report:

```text
artifacts/final-qa-20260518T021032Z.json
```

Latest observed results:

- `npm run harness`: PASS
- build: PASS, only Vite chunk-size warning from bundled Three.js
- dist size: 0.531 MB
- source bundle excluding node_modules/.git: 14.427 MB
- representative evidence PNGs under 5MB
- required files present

## Browser evidence

Latest clean 2-view no-background-noise screenshots:

```text
artifacts/evidence/front-goose-2view-common-20260518.png
artifacts/evidence/right-nubzuki-2view-common-20260518.png
```

Current evidence JSON:

```text
artifacts/final-qa-20260518T021032Z.json
```

Older color/glow evidence exists, but after the 3-view revert the clean common-point evidence above is the safer baseline.

## Current source map

- `src/main.ts`: viewer UI, mask extraction, shared point-cloud generation, quantile row materialization, endpoint color attributes, cosine directional shader color, view controls, capture controls, runtime QA.
- `src/contestRules.ts`: KAIST rule summary displayed in the app.
- `scripts/shared-space-harness.mjs`: regression harness for the 2-view no-projection-only invariant.
- `scripts/final-qa.mjs`: artifact/package size and required-file sanity report.
- `README.md`: current run instructions, invariant, evidence, and roadmap.
- `writeup/writeup.md`: updated current write-up draft for the 2-view lenticular point-cloud direction.
- `project_proposal.md`: originally written for the older perceptual-room direction; now has a current-status warning at the top.

## Latest color pass result

Implemented the requested quality pass:

```text
2-view로 넙죽이와 거위 색까지 표현해서 제대로 만들어줘라.
```

What changed:

- Reference mask extraction now flood-fills white page background from the canvas edges, so enclosed white object regions remain active.
- Each row sample carries RGB from the reference image, not only an x/z coordinate.
- Each shared 3D point stores endpoint RGB attributes from the paired front/side reference pixels; the shader computes cosine directional color from the camera direction.
- Density was raised from `SAMPLE_STRIDE=2`, `ROW_COUNT=150` to `SAMPLE_STRIDE=1`, `ROW_COUNT=190`; current cloud has 18,102 shared points.
- Point size/framing were tightened for clearer canonical screenshots.
- No view-dependent opacity/geometry/texture swap was introduced.

Latest algorithm implementation checks:

- `npm run harness`: PASS
- `npm run harness:algorithm`: PASS
- `npm run harness:algorithm:require-production`: PASS
- `npm run qa:submission`: PASS, report `artifacts/final-qa-20260518T134151Z.json`
- Browser console in the dev app: no JS errors
- Runtime QA: `scenePointsCount=1`, shared geometry PASS, `projectionOnlyPointCount=0`, `noProjectionOnlyPoints=true`, `rowPolicy=quantile_max/sorted-midpoint-quantile`, `colorPolicy=cosine_s1-directional-color`

Latest algorithm evidence:

```text
artifacts/algorithm-implementation/front-quantile-directional-20260518.png
artifacts/algorithm-implementation/right-quantile-directional-20260518.png
artifacts/algorithm-implementation/reveal-quantile-directional-20260518.png
artifacts/algorithm-implementation/browser-qa-20260518.json
```

Observed quality:

- Front goose remains recognizable and now uses front endpoint colors in the front view.
- Right image/cake-side view is recognizable with endpoint color present.
- Remaining visual weakness: horizontal row banding/scanline artifacts and sparse/jagged edges are still visible; side coverage remains about 75.7% due to unmatched side-only rows.

## Next likely task

If continuing polish, target the remaining banding/noise without breaking the invariant:

- try jittered sub-row y placement inside each row while preserving projection readability,
- compare smaller splat size vs mild additive alpha,
- add automated canonical image similarity metrics,
- export a fresh final MP4 from the current color branch.

## Previous suggested implementation approach for color

Start with a small spike before changing the main renderer:

1. Sample actual RGB from both reference images at the matched `(x,y)` and `(z,y)` coordinates.
2. Because each physical point must have one fixed color, combine the two target colors with a deterministic policy:
   - weighted average if colors are compatible,
   - luminance-preserving blend,
   - or duplicate only within the same physical-coordinate generation rule if it does not create separate per-view layers.
3. Add QA fields for color policy, e.g. `colorPolicy`, `frontColorError`, `sideColorError`, if feasible.
4. Visually verify that color improves both views without softening silhouettes or adding background noise.
5. Keep point size/glow conservative; if the image becomes blurry, reduce glow before adding density.

## Scoring assessment

The clean 2-view shared point-cloud idea is stronger than the noisy 3-view attempt because it has a clear technical invariant and visible reveal. For better KAIST scoring, the project still needs:

- color fidelity that makes goose/nubzuki recognizable without relying on labels,
- final representative PNG and final MP4 from the current branch, not older historical videos,
- concise write-up explaining row-matched projection constraints,
- explicit browser evidence that there is one shared geometry and zero projection-only points,
- final polish pass on splat density, glow, camera framing, and UI clutter.
