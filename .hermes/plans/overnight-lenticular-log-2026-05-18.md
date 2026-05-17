# Overnight lenticular session log — 2026-05-18

## Baseline before unattended ticks

- Branch: `lenticular-shared-point-cloud`
- Commit: `74d43ac feat: implement shared lenticular point cloud`
- Implemented: single shared `THREE.BufferGeometry` point cloud, front/right orthographic views, PNG/WebM capture, UI invariant explanation.
- Verification: `npm run build` passed with only the known Three.js chunk-size warning; browser console had no JS errors; browser-vision confirmed front reads `WHAT WE SEE` and right reads `WHAT EXISTS` from the same cloud.
- Evidence:
  - `artifacts/lenticular-shared/front-what-we-see.png`
  - `artifacts/lenticular-shared/right-what-exists.png`

## Tick 1/6 — invariant QA export and documentation

- Slice: backlog #1, deterministic shared-cloud metrics and explicit invariant documentation.
- Changed files: `src/main.ts`, `src/styles.css`, `README.md`, `index.html`.
- Implemented: browser-console `window.__LENTICULAR_QA__` live getter with seed, mask dimensions, coverage, point count, projection labels, exact scene `THREE.Points` count, shared-geometry identity, explicit `position`/`color` attribute counts/item sizes, and `pointCloudInvariantHolds`; visible Invariant QA card; README inspection notes; updated stale page title/description to the lenticular point-cloud direction.
- Invariant status: physical cloud remains one `THREE.Points` object backed by one shared `THREE.BufferGeometry`; no separate text meshes, duplicate point clouds, per-view hidden layers, or opacity/depth-test reading tricks added.
- Verification:
  - `npm run build` PASS; only known Vite/Three.js chunk-size warning.
  - Spec review PASS; quality review APPROVED after strengthening attribute checks and live QA getter.
  - `git diff --check` PASS, with only Git LF→CRLF working-copy warnings.
  - Browser QA available: front view visually read `WHAT WE SEE`; right view visually read `WHAT EXISTS`; console QA reported `scenePointsCount: 1`, `pointCloudUsesSharedGeometry: true`, `pointCloudInvariantHolds: true`; no console errors observed before final title-only refresh. After title fix, browser title/QA getter rechecked; front page loaded with Invariant QA PASS.
- Commit: `71f8d12 chore: expose lenticular invariant qa`.
- Next step: improve legibility/density with measurable front/right screenshots in a unique artifact directory, preserving the same shared-cloud invariant.

