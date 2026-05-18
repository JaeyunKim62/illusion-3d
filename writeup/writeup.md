# One Cloud, Multiple Readings: 3D Lenticular Point Cloud

KAIST 3D Rendering Contest write-up draft

Teammate(s): Jaeyu Kim

## 1. Description

This project is a browser-rendered 3D lenticular point-cloud illusion. The scene contains one physical `THREE.BufferGeometry` point set only. Each point has one coordinate `(x, y, z)`, but different orthographic camera directions read different 2D projections of the same physical cloud:

```text
Front +Z view:  (x, y) -> goose reference image
Right +X view:  (z, y) -> nubzuki reference image
Back/Left:      mirrored projections of the same point set
```

The viewer can switch between fixed canonical views and a free 3D reveal/orbit mode. In canonical views, the same colored points organize into recognizable goose and nubzuki images. In reveal/orbit mode, the object is exposed as a sparse 3D cloud rather than separate billboards or hidden layers.

The core theme is that a single physical object can have multiple perceptual readings depending on projection direction.

## 2. Contest-rule posture

The implementation follows the KAIST 3D Rendering Contest constraints as a rules-first design requirement:

- Final rendering is done in the browser with WebGL/Three.js.
- No Blender rendering is used.
- No commercial or closed-source 3D tools are used.
- No external 3D meshes, scans, model files, or texture assets are imported.
- The goose/nubzuki reference images are local source/data inputs used as 2D masks for procedural point generation, not external 3D assets.
- Geometry, point matching, colors, shader glow, labels, camera controls, PNG capture, and WebM recording are generated from source code.
- Intended export targets are `representative.png` at 1920x1080 or smaller and under 5MB, and `output.mp4` at 10 seconds or shorter, 1920x1080 or smaller, and under 50MB.
- One browser 3D content package must remain under 100MB.

## 3. Technical aspects

### 3.1 Shared physical point-set invariant

The project deliberately avoids fake view-dependent readings. The implementation must satisfy:

```text
There is one point set P only.
For each p=(x,y,z) in P:
  Front +Z projection uses (x,y)
  Right +X projection uses (z,y)
```

Forbidden shortcuts:

- no second point cloud,
- no duplicate text/image mesh,
- no per-view opacity gate,
- no depth-test reading gate,
- no projection-only or fallback points for an extra view.

Runtime QA exposes this invariant in `window.__LENTICULAR_QA__`, including:

- `scenePointsCount === 1`,
- `pointCloudUsesSharedGeometry === true`,
- `projectionCount === 2`,
- `projectionOnlyPointCount === 0`,
- `noProjectionOnlyPoints === true`,
- `pointCloudInvariantHolds === true`.

### 3.2 Row-matched 2-view generation

The generator draws each reference image into a Canvas 2D mask and extracts active pixels into row bins. For a shared row `r`, it collects front x-coordinates and side z-coordinates:

```text
X_r = active front mask columns on row r
Z_r = active side mask columns on row r
```

It then generates:

```text
N_r = max(|X_r|, |Z_r|)
x_k = X_r[floor((k + 0.5) |X_r| / N_r)]
z_k = Z_r[floor((k + 0.5) |Z_r| / N_r)]
p_k^r = (x_k, y_r, z_k)
```

The shorter coordinate list is reused by sorted midpoint quantile indexing rather than shuffled modulo indexing. This keeps the denser image from being unnecessarily thinned while reducing row-order/reveal chaos.

### 3.3 Color and light

The current branch stores endpoint colors as `frontColor` and `sideColor` attributes and computes cosine directional color in the shader. This is a material/color response only: it does not hide points, swap texture, or change geometry by view. The current UI describes this as:

```text
colorSource: frontColor/sideColor endpoint attributes
colorPolicy: cosine_s1-directional-color
shaderGlowOnly: true
viewDependentOpacityGate: false
depthTestReadingGate: false
```

This improves endpoint color fidelity for both readings while preserving the one-cloud invariant. The current visual pass keeps a moderate row-spacing expansion (`POINT_SCALE_Y=1.28`) plus deterministic sub-row y jitter, subtle point-size jitter, and a softer/larger splat (`POINT_SIZE=2.65`, `POINT_ALPHA=0.68`) to reduce the harshness of the row-scanline look without adding points or view gates. A wider `POINT_SCALE_Y=1.38` spacing was rejected because the bands became too dominant, and an alpha-jitter variant was rejected because it added speckled noise without meaningful banding reduction. Future color passes must still avoid view-dependent opacity, hidden geometry, texture swaps, or duplicated point fields.

### 3.4 Viewer and capture controls

The browser viewer includes:

- `Front +Z: goose`,
- `Right +X: nubzuki`,
- `Back -Z: mirrored A`,
- `Left -X: mirrored B`,
- `3D reveal`,
- free OrbitControls,
- PNG capture,
- 10-second WebM recording.

## 4. Reproduction steps

```bash
npm install
npm run dev
# open http://127.0.0.1:5173
npm run harness
npm run qa:submission
```

Browser console QA:

```js
window.__LENTICULAR_QA__
```

Important harness:

```bash
node scripts/shared-space-harness.mjs
```

This harness fails if top/projection-only/fallback point paths are reintroduced. It enforces the clean 2-view common-point state after the failed 3-view attempt produced barcode-like background noise.

## 5. Current evidence

Current branch:

```text
reference-image-two-view
```

Important committed checkpoint:

```text
e94de25 test: enforce shared 2-view point space
```

Browser-verified evidence:

- `artifacts/evidence/front-goose-2view-common-20260518.png`
- `artifacts/evidence/right-nubzuki-2view-common-20260518.png`
- `artifacts/final-qa-20260518T020849Z.json`

Recent QA values from the 2-view common-point state:

- points: about 3,805,
- matched rows: 81/150,
- active-row overlap: about 95.3%,
- front coverage: 100%,
- side coverage: 100%,
- projection-only point count: 0.

## 6. Limitations and next improvements

- The 2-view common-point invariant is now protected by harness and should not be weakened.
- The previous 3-view KAIST projection route was removed because projection-only top points leaked as barcode-like background noise in other views.
- The next quality task is to make goose and nubzuki color more faithful and visually stronger while keeping one shared `BufferGeometry`.
- Better contest scoring likely needs final visual polish: denser/cleaner splats, improved color reconstruction, a representative PNG, final 10-second MP4, and a concise technical explanation of the shared-projection algorithm.
- A true 3-view version should only be attempted with a real common-point solver and explicit signal/noise metrics; do not append projection-only points.

## 7. References

- KAIST 3D Rendering Contest instructions and submission constraints.
- Three.js documentation for WebGLRenderer, OrthographicCamera, BufferGeometry, ShaderMaterial, Points, OrbitControls, and Canvas capture APIs.
- Vite and TypeScript documentation for browser build tooling.
- HTML Canvas 2D API for reference-image mask sampling.
- ffmpeg/ffprobe documentation for optional WebM-to-MP4 conversion and media validation.
