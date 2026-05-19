# One Cloud, Multiple Readings: Material-State Lenticular Point Cloud

Browser/WebGL implementation for the KAIST 3D Rendering Contest. The current artifact is a single shared `THREE.BufferGeometry` point cloud whose front/right orthographic readings are extended with small-angle material-state lenticular changes.

## Current result

The production candidate on this branch is:

```text
quantile_max shared point cloud
+ cosine_s1 front/right directional color
+ delta_lobe_s1 material-state lobes
```

Visual states:

- `Front +Z`: Nubzuki with white heart and white KAIST marking.
- `Front +2°`: the same fixed Nubzuki support with red heart and red KAIST marking.
- `Right +X`: Kumdori base state.
- `Right +2°`: the same fixed Kumdori support with red antenna/star tip and redder cheeks.

The `-down` filenames are historical. In this branch they mean alternate material/color state, not pose-down geometry.

## Critical invariant

There is one physical point set only.

```text
For each point p=(x,y,z):
  Front +Z projection uses (x,y) and should read Nubzuki.
  Right +X projection uses (z,y) and should read Kumdori.
```

Allowed:

- one contest `THREE.Points` object;
- one shared `THREE.BufferGeometry` for the contest cloud;
- fixed per-point positions;
- fixed per-point color/material attributes;
- shader-only glow/splat styling;
- helper axes/grid/labels as diagnostics only.

Forbidden:

- second point cloud for the second reading;
- hidden image/text billboards;
- projection-only, fallback, top-only, or third-view-only points;
- view-dependent opacity gates;
- depth-test reading gates;
- texture swaps or per-view geometry swaps.

## Run and verify

```bash
npm install
npm run dev
# open http://127.0.0.1:5173
npm run harness:algorithm
npm run harness:algorithm:require-production
npm run harness
```

`npm run harness` runs the shared-space invariant harness and `npm run build`. A Vite chunk-size warning can appear because Three.js is bundled; it is not a build failure.

Runtime QA is exposed in the browser console:

```js
window.__LENTICULAR_QA__
```

Important expected fields:

```text
scenePointsCount = 1
pointCloudUsesSharedGeometry = true
projectionOnlyPointCount = 0
noProjectionOnlyPoints = true
visualStyle.viewDependentOpacityGate = false
visualStyle.textureSwap = false
visualStyle.geometrySwapCount = 0
pointCloudInvariantHolds = true
```

## Added lenticular algorithm

Each fixed point stores four color basis attributes sampled from the reference images:

```text
frontBaseColor = sample(nubzuki.png,      x, y)
frontDownColor = sample(nubzuki-down.png, x, y)
sideBaseColor  = sample(kumdori.png,      z, y)
sideDownColor  = sample(kumdori-down.png, z, y)
```

The shader computes camera signed azimuth:

```text
theta = atan2(camera.x, camera.z)
```

Endpoint meanings:

```text
0°   = Front +Z base
2°   = Front +Z alternate red state
90°  = Right +X base
92°  = Right +X alternate red-accent state
```

For a base center `b`, alternate center `a`, and `sigma = 0.9°`:

```text
G(theta, c) = exp(-0.5 * ((theta - c) / sigma)^2)
altWeight(theta) = G(theta, a) / (G(theta, b) + G(theta, a))
```

The per-view material states are:

```text
C_front = mix(frontBaseColor, frontDownColor, frontAltWeight)
C_side  = mix(sideBaseColor,  sideDownColor,  sideAltWeight)
```

Then the existing front/right directional blend is applied:

```text
C_final = frontViewWeight(theta) * C_front
        + sideViewWeight(theta)  * C_side
```

This is a fixed-geometry material-state lenticular. It is not a 4-view geometric reconstruction solver.

## Point generation summary

The 3D point set still uses row-wise `quantile_max` materialization. For each matched row `y`:

```text
X_y = sorted active front x samples
Z_y = sorted active side z samples
N_y = max(|X_y|, |Z_y|)

x_k = X_y[floor((k + 0.5) |X_y| / N_y)]
z_k = Z_y[floor((k + 0.5) |Z_y| / N_y)]
p_k = (x_k, y, z_k)
```

This preserves one shared physical support while covering both front and side active rows as evenly as possible.

## Viewer controls and capture

- `Front +Z: nubzuki`: front base state.
- `Front +2°: nubzuki-down`: front red material state.
- `Right +X: kumdori`: right base state.
- `Right +2°: kumdori-down`: right red-accent material state.
- `Back −Z: mirrored A`: diagnostic mirrored front projection.
- `Left −X: mirrored B`: diagnostic mirrored side projection.
- `3D reveal`: oblique view of the one physical cloud.
- `자유 Orbit`: interactive inspection.
- `PNG 캡처`: downloads `lenticular-<view>.png`.
- `10초 WebM 녹화`: records +Z white→red, +X normal→red-accent, then positive-Z overhead reveal.

The recording path intentionally avoids the old `−Z` mirrored-front reveal. It stays on the positive-Z side for the final reveal.

## Asset strategy and limitations

This branch rejected large pose/silhouette changes such as lowering an arm. With fixed positions and no opacity gate, a pose change cannot create points at a new silhouette location or hide points at the old location. It reads as color smear/ghosting rather than motion.

Good alternate-state assets:

- same silhouette;
- same bbox/alignment;
- same pose;
- strong internal color/marking changes;
- broad shapes instead of thin detail.

Poor alternate-state assets:

- arm/leg/body pose changes;
- new silhouette support;
- thin text at small scale;
- semi-transparent edge backgrounds;
- mismatched image size/alignment.

Known visual limits:

- The alternate state is a soft lobe, not a hard 100% switch.
- Small typography remains affected by point-cloud/scanline sampling.
- Mid-arc views blend the front and side readings.
- This is best described as `fixed one-cloud + directional material/color lobe`.

## Current evidence

Final material-state evidence lives under:

```text
artifacts/delta-lenticular/final-material-state-20260519/
```

Earlier exploratory evidence and rejected pose/down experiments may exist under `artifacts/delta-lenticular/` for comparison only.

## Source map

- `src/main.ts`: reference image loading, shared point-cloud generation, four-lobe material attributes, shader, viewer controls, PNG/WebM capture, runtime QA.
- `scripts/algorithm-parity-harness.mjs`: source/classification and math checks for `quantile_max`, `cosine_s1`, and `delta_lobe_s1`.
- `scripts/shared-space-harness.mjs`: one-cloud/no-projection-only invariant and build harness used by `npm run harness`.
- `scripts/final-qa.mjs`: package/artifact sanity report.
- `artifacts/reference-image/`: base and alternate reference images used by the current viewer.
- `CURRENT_HANDOFF.md`: compact handoff with final state, validation, limits, and next steps.

## Final submission checklist

- [ ] Run `npm run harness:algorithm:require-production` and `npm run harness`.
- [ ] Browser console has no JavaScript errors in front/front+2/right/right+2/reveal views.
- [ ] Export representative PNG at <=1920x1080 and <=5MB.
- [ ] Export/convert output MP4 at <=10s, <=1920x1080, and <=50MB.
- [ ] Package one browser 3D content bundle under 100MB.
- [ ] Include source/data and cite Three.js, Vite/TypeScript, Canvas API usage, and contest rules in the final write-up.
- [ ] Re-check no external 3D assets, no Blender rendering, and no commercial/closed 3D tools are introduced.

## Dependencies and references

- Three.js / WebGL for browser rendering and OrbitControls.
- Vite and TypeScript for local development/build tooling.
- HTML Canvas 2D API for reference image sampling.
- ffmpeg is optional for local WebM-to-MP4 conversion; it is not part of the browser 3D content.
