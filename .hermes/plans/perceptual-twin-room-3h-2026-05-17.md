# 3-hour autonomous implementation plan: Perceptual Twin Room

Source spec: `project_proposal.md`

## Goal
Finish a strong browser-viewable MVP for `What We See Is Not What Exists: A Perceptual Twin Room` within a 3-hour loop, preserving KAIST contest constraints:
- WebGL/Three.js rendering, no Blender rendering.
- No external 3D assets.
- Procedural/handcrafted geometry and procedural materials.
- Reproducible source/config.
- Browser viewer must demonstrate the result.

## Fixed harness
- `npm run harness` (currently aliases `npm run build`).
- Browser smoke: open `http://127.0.0.1:5173`, check console errors, capture/inspect reference and reveal views when visual code changes.

## Current completed baseline
- Reference camera/render camera separation.
- `backprojectNDC`, `projectToNDC`, pixel reprojection error display.
- Anamorphic `WHAT WE SEE` text pieces from Canvas mask sampling and ray back-projection.
- Distorted room mesh from 2D layout corners + asymmetric depth assignment.
- Same-size spheres at different depth.
- Technical overlay: rays, camera helper/frustum, ghost perceived box.
- 10-second timeline, reference/reveal/orbit/wire controls, PNG/WebM capture.
- Verified browser screenshots:
  - `artifacts/perceptual-twin-mvp-reference.png`
  - `artifacts/perceptual-twin-mvp-reveal.png`

## Remaining priority slices
1. UI state and overlay polish
   - Active button state for reference/reveal/orbit/wire.
   - Separate ray/frustum/ghost/wire visibility or reduce overlay opacity.
   - Acceptance: reveal view is understandable and not cluttered.

2. Visual quality pass
   - Improve composition, lighting, color, text readability, room silhouette.
   - Add labels: Reference Camera / Physical Twin / Perceptual Twin / same physical size.
   - Acceptance: silent viewer explains itself from reference and reveal screenshots.

3. Capture/export polish
   - Ensure WebM record starts from t=0 and stops <=10s.
   - Add instructions for ffmpeg MP4 conversion and output constraints.
   - Acceptance: README documents representative PNG/output MP4 flow.

4. Technical reproducibility/docs
   - README with rules, run/build, architecture, formulas, dependencies/references.
   - Write-up draft under `writeup/writeup.md` with required sections.
   - Acceptance: evaluator can understand why this is inverse projection, not static art.

5. Final QA
   - `npm run harness` green.
   - Browser console has no JS errors.
   - Reference view: text readable, room normal-looking.
   - Reveal view: distorted geometry + rays/frustum visible.
   - File size sanity check for built content/artifacts.

## Per-tick rules
- One coherent slice per tick.
- Run `npm run harness` before claiming completion.
- For visual changes, use browser verification and save screenshots under unique `artifacts/` names.
- Do not use destructive cleanup of evidence artifacts.
- Append to `.hermes/plans/perceptual-twin-room-3h-log-2026-05-17.md` after every tick.
