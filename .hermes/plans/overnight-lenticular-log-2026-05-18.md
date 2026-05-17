# Overnight lenticular session log — 2026-05-18

## Baseline before unattended ticks

- Branch: `lenticular-shared-point-cloud`
- Commit: `74d43ac feat: implement shared lenticular point cloud`
- Implemented: single shared `THREE.BufferGeometry` point cloud, front/right orthographic views, PNG/WebM capture, UI invariant explanation.
- Verification: `npm run build` passed with only the known Three.js chunk-size warning; browser console had no JS errors; browser-vision confirmed front reads `WHAT WE SEE` and right reads `WHAT EXISTS` from the same cloud.
- Evidence:
  - `artifacts/lenticular-shared/front-what-we-see.png`
  - `artifacts/lenticular-shared/right-what-exists.png`

