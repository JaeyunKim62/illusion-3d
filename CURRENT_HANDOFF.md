# Current handoff — material-state lenticular point cloud

Date: 2026-05-19
Branch: `delta-lenticular-lobes-20260519`

## Current direction

The current artifact is a browser/WebGL KAIST rendering demo built from one shared 3D point cloud. The latest work adds a small-angle material-state lenticular effect on top of the existing front/right readings.

Final visual story:

```text
+Z base:      Nubzuki, white heart and white KAIST
+Z micro +2°: Nubzuki, red heart and red KAIST
+X base:      Kumdori, normal state
+X micro +2°: Kumdori, red antenna/star and redder cheeks
```

The `-down` filenames are historical. They now mean alternate color/material state, not pose-down geometry.

## Non-negotiable invariant

Keep exactly one physical point cloud.

Allowed:

- one `THREE.Points` object for the contest object;
- one shared `THREE.BufferGeometry`;
- fixed per-point `position`;
- fixed per-point color/material attributes: `frontBaseColor`, `frontDownColor`, `sideBaseColor`, `sideDownColor`;
- shader glow/splat styling;
- helper axes/grid/labels as non-reading diagnostics.

Forbidden:

- second point cloud for the second image/state;
- hidden image/text billboards;
- view-dependent opacity gates;
- depth-test reading gates;
- texture swaps;
- per-view geometry swaps;
- projection-only/fallback points that exist for only one view.

## Added algorithm

The added algorithm is `delta_lobe_s1` material-state blending.

Each point `p=(x,y,z)` stores four color basis samples:

```text
frontBaseColor = sample(nubzuki.png,      x, y)
frontDownColor = sample(nubzuki-down.png, x, y)
sideBaseColor  = sample(kumdori.png,      z, y)
sideDownColor  = sample(kumdori-down.png, z, y)
```

Camera signed azimuth:

```text
theta = atan2(camera.x, camera.z)
```

Lobe centers:

```text
front base = 0°
front alt  = 2°
side base  = 90°
side alt   = 92°
sigma      = 0.9°
```

For a base center `b` and alternate center `a`:

```text
G(theta, c) = exp(-0.5 * ((theta - c) / sigma)^2)
altWeight = G(theta, a) / (G(theta, b) + G(theta, a))
```

The shader first computes per-view material state colors, then applies the existing front/right directional blend:

```text
C_front = mix(frontBaseColor, frontDownColor, frontAltWeight)
C_side  = mix(sideBaseColor,  sideDownColor,  sideAltWeight)
C_final = frontViewWeight(theta) * C_front + sideViewWeight(theta) * C_side
```

## Asset decisions

Rejected direction:

- Nubzuki arm/hand-down pose change.
- Reason: fixed positions plus no opacity gate cannot move silhouette support. The result looked different, but not like a real arm pose change.

Accepted direction:

- same silhouette, same pose, same bbox;
- internal material/color changes only.

Current assets:

```text
artifacts/reference-image/nubzuki.png
artifacts/reference-image/nubzuki-down.png
artifacts/reference-image/kumdori.png
artifacts/reference-image/kumdori-down.png
```

Backups kept for context:

```text
artifacts/reference-image/nubzuki-down.pose-backup.png
artifacts/reference-image/kumdori-down.pose-backup.png
artifacts/reference-image/nubzuki.heart-original-backup.png
```

## Viewer / recording

Viewer buttons include:

- `Front +Z: nubzuki`
- `Front +2°: nubzuki-down`
- `Right +X: kumdori`
- `Right +2°: kumdori-down`
- `Back −Z: mirrored A` and `Left −X: mirrored B` as diagnostics
- `3D reveal`
- `자유 Orbit`

10-second WebM path:

```text
+Z Nubzuki white state hold
→ +Z micro red heart/KAIST hold
→ smooth +Z to +X arc
→ +X Kumdori normal hold
→ +X micro red antenna/cheeks hold
→ positive-Z overhead reveal
```

The old recording path that moved to `−Z` mirrored front was removed from the main recording story.

## Latest verification

Latest checked commands:

```bash
npm run harness:algorithm:require-production
npm run harness
```

Observed result:

- algorithm harness PASS;
- production algorithm harness PASS;
- shared-space/no-background-noise harness PASS;
- build PASS;
- only Vite chunk-size warning from bundled Three.js.

Runtime QA expectations:

```text
scenePointsCount = 1
pointCloudUsesSharedGeometry = true
projectionOnlyPointCount = 0
noProjectionOnlyPoints = true
viewDependentOpacityGate = false
textureSwap = false
geometrySwapCount = 0
pointCloudInvariantHolds = true
frontActiveIoU ≈ 1.0
frontFallbackRatio = 0.0%
sideActiveIoU ≈ 1.0
sideFallbackRatio = 0.0%
```

## Current evidence

Final material-state evidence should be kept in:

```text
artifacts/delta-lenticular/final-material-state-20260519/
```

Earlier exploratory screenshots in `artifacts/delta-lenticular/` include rejected or intermediate states and should not be treated as final quality claims unless explicitly named as such.

## Known limitations

- This is not a 4-view geometric reconstruction solver.
- It does not support large pose/silhouette changes such as lowering an arm.
- The micro-angle transition is soft, not a hard binary switch.
- Thin lettering can be softened by point-cloud/scanline sampling.
- Mid-arc views blend front and side readings.
- Best description: `fixed one-cloud + directional material/color lobe`.

## Source map

- `src/main.ts`: main implementation, four-lobe material-state shader, viewer and recording path.
- `scripts/algorithm-parity-harness.mjs`: checks `quantile_max`, `cosine_s1`, and `delta_lobe_s1` source/math properties.
- `scripts/shared-space-harness.mjs`: one-cloud/no-projection-only invariant and build harness.
- `README.md`: user-facing run/algorithm/limitations summary.
- `artifacts/reference-image/`: final base/alt reference images and backups.
