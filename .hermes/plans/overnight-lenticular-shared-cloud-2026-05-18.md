# Overnight plan: shared 3D lenticular point cloud

Branch: `lenticular-shared-point-cloud`
Repo: `C:/00_Codes/illusion-3d`

## Non-negotiable invariant

One physical point set only. Do not reintroduce separate text meshes, duplicate point clouds, per-view hidden layers, or opacity gating to fake readings.

For every point `p=(x,y,z)`:

- Front +Z / `(x,y)` must read `WHAT WE SEE`.
- Right +X / `(z,y)` under the viewer convention must read `WHAT EXISTS`.
- Back/left are mirrored views of the same points unless an explicit approximate 4-view experiment is isolated and labelled as such.

## Fixed harness

- `npm run build`
- Browser QA if available: front screenshot reads `WHAT WE SEE`; right screenshot reads `WHAT EXISTS`; console has no JS errors.
- Preserve artifacts in unique directories under `artifacts/`; do not delete evidence.

## Backlog order

1. Add/verify deterministic shared-cloud metrics and make the invariant more explicit in UI/write-up.
2. Improve legibility and point density without breaking the single-cloud invariant.
3. Add automated or semi-automated orthographic capture/evaluation helpers if feasible.
4. Prototype an approximate 4-view mode only if it is clearly labelled experimental and does not replace the proven 2-view implementation.
5. Explore color/light extensions while keeping identity of the points fixed.
6. Update `writeup/writeup.md` and project proposal notes for the new 3D lenticular point-cloud direction.

## Tick protocol

Each tick:

1. Inspect `git status --short --branch` and this plan/log.
2. Choose one coherent slice from the backlog.
3. Implement only if it can be verified in the tick.
4. Run the fixed harness.
5. If green and coherent, commit with a concise message.
6. Append `.hermes/plans/overnight-lenticular-log-2026-05-18.md` with changed files, verification, commit hash, and next step.
7. If blocked or harness fails, do not commit broken code; log the blocker.
