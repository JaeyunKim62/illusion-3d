# One Cloud, Multiple Readings: 3D Lenticular Point Cloud

Browser/WebGL implementation for the KAIST 3D Rendering Contest. The core artifact is a single shared `THREE.BufferGeometry` point cloud: every point has one physical coordinate `(x,y,z)`. From the front orthographic view the projection `(x,y)` reads the goose reference image; from the right orthographic view the projection `(z,y)` reads the nubzuki reference image. Back/left views show the same physical points as mirrored projections.

## KAIST rule posture

- Renderer: Three.js/WebGL in the browser.
- No Blender rendering.
- No commercial or closed 3D tools.
- No external 3D assets, meshes, scans, or textures.
- Geometry, text masks, point matching, shader materials, labels, and captures are generated from source code.
- Required submission targets from the proposal: representative PNG <= 1920x1080 and <= 5MB; MP4 <= 10s, <= 1920x1080, <= 50MB; one 3D content package <= 100MB; source/data and write-up included.

## Critical invariant

This branch intentionally removes the earlier incorrect “two overlapping text fields” approach.

Required condition:

```text
There is one point set P only.
For each p=(x,y,z) in P:
  Front +Z image uses (x,y) -> goose reference image
  Right +X image uses (z,y) -> nubzuki reference image
```

No second point cloud, no duplicate text mesh, and no view-dependent opacity gate is used to fake the two readings.

The visible `Invariant QA` score card reports the runtime check for the physical cloud only: exactly one `THREE.Points` object, backed by the one shared `THREE.BufferGeometry`. Helper axes/grid lines can own separate line geometries for inspection, but they are not point sets and are excluded from the point-cloud invariant.

## Run and verify

```bash
npm install
npm run dev
# open http://127.0.0.1:5173
npm run harness
```

`npm run harness` currently runs TypeScript checking and a Vite production build. A Vite chunk-size warning can appear because Three.js is bundled; it is not a build failure.

Browser console invariant/metrics export:

```js
window.__LENTICULAR_QA__
```

The object is deterministic for the generated shared cloud and recomputes when read from the console. It includes the RNG seed, mask dimensions, row count, point count, front/side coverage, rows used, projection labels, scene `THREE.Points` count, shared-geometry identity check, explicit `position`/`color` attribute counts and item sizes, fixed per-point color/glow style metadata, and `pointCloudInvariantHolds` boolean. It also exposes `rowBalance`, a deterministic density/legibility QA block computed from the same sampled mask rows before/while generating the one physical point set:

```js
window.__LENTICULAR_QA__.rowBalance
// {
//   activeRows: { front, side, matched },
//   matchedRowRatio, // active-row overlap: matched / (frontOnly + sideOnly + matched)
//   rowMismatches: { frontOnly, sideOnly, emptyBoth },
//   generatedPointsPerMatchedRow: { min, median, max },
//   activePixels: { front, side } // sampled active mask positions after SAMPLE_STRIDE
// }
```

These row-balance/density numbers are QA metrics only: they do not add point clouds, hidden layers, text meshes, view-dependent opacity gates, or alternate geometry. They describe how many rows from the two masks can be matched into the single shared `THREE.BufferGeometry`, and how dense those matched rows are for legibility tuning. Expected high-level result: `scenePointsCount === 1`, `pointCloudUsesSharedGeometry === true`, `geometryAttributes.names` is `["color", "position"]`, and `pointCloudInvariantHolds === true`.

For final submission sanity checks, run:

```bash
npm run qa:submission
```

## Viewer controls

- `Front +Z: goose`: orthographic front projection of the shared cloud.
- `Right +X: nubzuki`: orthographic side projection of the same cloud.
- `Back −Z: mirrored A`: same cloud, mirrored front projection.
- `Left −X: mirrored B`: same cloud, mirrored side projection.
- `3D reveal`: oblique camera showing that the object is a scattered 3D cloud.
- `자유 Orbit`: inspect the physical point cloud interactively.
- `PNG 캡처`: downloads `lenticular-<view>.png` from the current canvas.
- `10초 WebM 녹화`: records a 10-second rotation through the canonical directions.

## Algorithm

1. Draw target reference images into deterministic Canvas 2D masks; text masks remain as a fallback path for development.
2. Extract active pixels into row bins.
3. For each row `r`, collect front x-coordinates `X_r` and side z-coordinates `Z_r`.
4. Generate `N_r = max(|X_r|, |Z_r|)` shared 3D points, reusing the shorter row modulo its sampled coordinates so the denser view is not unnecessarily thinned:

```text
p_i^r = (x_i, y_r, z_i)
```

The current implementation uses the side coordinate sign needed by the Three.js +X camera convention so the right-view screen reads left-to-right.

## Current evidence

Browser-verified screenshots and video:

- `artifacts/current-video/lenticular-shared-cloud-current.mp4` — MP4 capture of the previous text-based shared-cloud state, converted from the browser WebM capture and kept under the KAIST MP4 size limit.
- Historical text-cloud baseline kept for comparison only: `artifacts/lenticular-shared/front-what-we-see.png` and `artifacts/lenticular-shared/right-what-exists.png`.
- `artifacts/reference-image/goose.jpg` and `artifacts/reference-image/nubzuki.jpg` — reference images used by the current `reference-image-two-view` branch.
- `artifacts/reference-image-two-view/front-goose-color.png` — browser-verified colored Front +Z goose projection.
- `artifacts/reference-image-two-view/right-nubzuki-color.png` — browser-verified colored Right +X nubzuki projection.
- `artifacts/lenticular-color-light-tick3-20260518T011500Z/front-goose-color-light-page.png` — Tick 3 browser QA page screenshot for the color/glow front view.
- `artifacts/lenticular-color-light-tick3-20260518T011500Z/right-nubzuki-color-light-page.png` — Tick 3 browser QA page screenshot for the color/glow right view.
- `artifacts/lenticular-color-light-tick3-20260518T011500Z/browser-qa-summary.json` — Tick 3 invariant/style/browser-console summary.

Viewer metric format displayed at runtime:

```text
same points: <count> / matched rows: <matched>/<total> / active-row overlap: <ratio>% / row density min-med-max: <min>-<median>-<max> / coverage F/S: <front>%/<side>%
Physical cloud: 1 THREE.Points object using 1 shared BufferGeometry (...). Row QA: active rows F/S/M=<front>/<side>/<matched>; drops F-only/S-only/empty=<frontOnly>/<sideOnly>/<emptyBoth>; sampled active pixels F/S=<front>/<side>. Style QA: fixed-per-point-attribute, shaderGlowOnly=true, viewOpacityGate=false, depthGate=false. ... Point-cloud invariant: PASS.
```

## Extension roadmap

- 4-view: exact independent north/east/south/west images are over-constrained for one `(x,y,z)` point set. Implement approximate 4-view matching with more points, row/column/voxel compatibility scoring, and explicit signal/noise metrics.
- Color changes: current slice uses fixed per-point color attributes plus shader glow only; future color experiments must preserve point identity and must not swap geometry or opacity-gate readings.
- Light/shading: compare additive `THREE.Points`, Gaussian/sprite splats, and instanced tiny spheres for better contest rendering.
- Evaluation: add automated orthographic captures and image-mask similarity metrics for each canonical view.

## Source map

- `src/main.ts`: shared point-cloud generation, Canvas reference-image/text-fallback masks, row matching, fixed per-point color attributes, Three.js orthographic viewer, PNG/WebM capture.
- `src/contestRules.ts`: durable KAIST rule summary displayed in the app.
- `src/styles.css`: browser UI and capture-status styling.
- `scripts/final-qa.mjs`: timestamped final-submission sanity report for artifact/file/bundle size checks.
- `scene_config.json`: legacy render/camera parameters retained for compatibility; current shared-cloud constants live in `src/main.ts`.
- `project_proposal.md`: original Korean proposal plus a current-status warning; historical content below the warning is not authoritative for the present branch.
- `CURRENT_HANDOFF.md`: compact Korean/English handoff for `/new`, including invariant, harness, evidence, and the next color task.
- `writeup/writeup.md`: current submission write-up draft for the 2-view lenticular point-cloud direction.
- `artifacts/`: preserved browser evidence screenshots.

## Final submission checklist

- [ ] Run `npm run harness` and confirm build passes.
- [ ] Browser console has no JavaScript errors in front/right/reveal views.
- [ ] Export representative PNG at <=1920x1080 and <=5MB.
- [ ] Export/convert output MP4 at <=10s, <=1920x1080, and <=50MB.
- [ ] Package one browser 3D content bundle under 100MB.
- [ ] Include source/data and cite Three.js, Vite/TypeScript, Canvas API usage, and contest rules in the final write-up.
- [ ] Re-check no external 3D assets, no Blender rendering, and no commercial/closed 3D tools are introduced.

## Dependencies and references

- Three.js / WebGL for browser rendering and OrbitControls.
- Vite and TypeScript for local development/build tooling.
- HTML Canvas 2D API for procedural text mask sampling.
- ffmpeg is optional for local WebM-to-MP4 conversion; it is not part of the browser 3D content.
- KAIST 3D Rendering Contest rules summarized in `project_proposal.md` and `src/contestRules.ts`.
