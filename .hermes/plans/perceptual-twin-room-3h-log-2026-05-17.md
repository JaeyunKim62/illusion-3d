# Perceptual Twin Room 3-hour session log — 2026-05-17

## Tick 0 — bootstrap MVP
- Why: user asked to begin implementation from `project_proposal.md` and continue iterating toward the goal for 3 hours.
- Files changed: `package.json`, `package-lock.json`, `scene_config.json`, `index.html`, `src/main.ts`, `src/styles.css`, `artifacts/perceptual-twin-mvp-reference.png`, `artifacts/perceptual-twin-mvp-reveal.png`, plan/log files.
- Implemented: Three.js procedural scene, inverse projection helpers, reprojection error display, anamorphic text pieces, distorted room, same-size spheres, technical overlay, timeline/capture controls.
- Verification:
  - `npm run build`: PASS, with Vite chunk-size warning only.
  - Browser reference view: PASS; `WHAT WE SEE` readable, room/spheres visible, console errors none.
  - Browser reveal view: PASS; distorted geometry and rays/frustum overlay visible, console errors none.
- Known issues:
  - Overlay is visually cluttered in reveal mode.
  - Buttons do not show active/toggled state.
  - Docs/write-up not yet created.
- Next slice: UI state and overlay polish, then README/write-up/export docs.

## Tick 1 — UI state and overlay polish (2026-05-17 18:24)
- Slice: priority 1, UI state and overlay polish.
- Changed files: `src/main.ts`, `src/styles.css`, generated `dist/*` from build, new evidence screenshot `artifacts/perceptual-twin-ui-overlay-polish-reveal-20260517-182427.png`.
- Implemented:
  - Added explicit `ViewMode` / `OverlayMode` state for play, reference, reveal, orbit, and overlay controls.
  - Added active/toggled button styling with `aria-pressed` updates.
  - Split debug overlay into separate `ghostOverlay`, `rayOverlay`, and `frustumOverlay` groups.
  - Replaced all-or-nothing `Wire/rays` with `Overlay: Off → Ghost → Rays → All`, so reveal defaults to less-cluttered Ghost mode while orbit can show All.
  - Reduced sampled text-ray count/opacity and added concise overlay help text.
- Verification:
  - `npm run harness`: PASS; Vite chunk-size warning only (`index-BgJbFvc9.js` > 500 kB).
  - Browser smoke at `http://127.0.0.1:5173`: PASS; reference/reveal loaded with no console JS errors.
  - Visual inspection: reference button active and clean; reveal button active with `Overlay: Ghost`, clutter reduced versus full rays/frustum.
- Known issues:
  - UI panel can feel vertically tight in the screenshot viewport, though it is scrollable.
  - Vite chunk-size warning remains non-blocking.
  - Overlay cycle affordance is text-only; future polish could add small mode chips/legend.
- Next slice: visual quality pass — stronger composition, labels/text readability, room silhouette, and silent-view understanding.

## Tick 2 — visual quality pass (2026-05-17 18:32)
- Slice: priority 2, visual quality pass for composition, labels, room silhouette, and silent-view understanding.
- Changed files: `src/main.ts`, `src/styles.css`, generated `dist/*` from build, evidence screenshots `artifacts/perceptual-twin-visual-quality-reveal-20260517-183001.png` and `artifacts/perceptual-twin-visual-quality-reveal-20260517-183253.png`.
- Implemented:
  - Added procedural canvas-sprite labels for `Physical Twin`, `Perceptual Twin`, `Reference Camera`, and same-size sphere explanation; no external assets introduced.
  - Added a subtle physical-room silhouette line overlay from the actual distorted room vertices to strengthen reveal readability.
  - Added a bottom story strip (`align → normal room → distorted reveal`) so the scene is understandable without audio.
  - Repositioned/reduced labels after visual inspection found the first physical label clipped and the reference view slightly busy.
  - Hid the physical distortion label in clean reference mode while keeping the same-size sphere cue visible.
- Verification:
  - `npm run harness`: PASS; Vite chunk-size warning only (`index-gQE54EA0.js` > 500 kB).
  - Browser reveal smoke at `http://127.0.0.1:5173`: PASS; no console JS errors.
  - Browser visual inspection: reveal labels are readable and no longer clipped; distorted room/reveal intent is understandable; active reveal state and `Overlay: Ghost` remain clear.
  - Browser reference inspection: `WHAT WE SEE` remains readable and the room still reads as normal; label clutter reduced by hiding the physical distortion label in reference mode.
- Known issues:
  - Right control panel can still extend below shorter screenshots, but it is scrollable.
  - `WHAT WE SEE` is readable but still slightly fragmented at the left edge; future pass could improve text contrast/spacing.
  - Vite chunk-size warning remains non-blocking.
- Next slice: capture/export polish — robust 10s WebM behavior and README/ffmpeg MP4 conversion instructions.

## Tick 3 — capture/export polish (2026-05-17 18:40)
- Slice: priority 3, capture/export polish for bounded 10s WebM behavior and MP4 conversion instructions.
- Changed files: `src/main.ts`, `src/styles.css`, `README.md`, generated `dist/*` from build, evidence screenshot `artifacts/perceptual-twin-capture-export-polish-reveal-20260517-183904.png`.
- Implemented:
  - Added capture status UI and recording button state (`Recording 10s…`, disabled button, completion status with WebM size).
  - Made WebM capture start the camera timeline explicitly from `t=0`, use configured `fps`/`durationSec`, choose a supported WebM MIME type, ignore empty chunks, stop tracks after completion, and return to reveal/ghost view.
  - Added browser fallback/error status when MediaRecorder/canvas capture is unavailable.
  - Added README capture/export flow with KAIST constraints, WebM-to-MP4 ffmpeg command, and ffprobe size/duration check.
- Verification:
  - `npm run harness`: PASS; Vite chunk-size warning only (`index-BjDGWRAV.js` > 500 kB).
  - Browser smoke at `http://127.0.0.1:5173`: PASS; no console JS errors.
  - Visual inspection: reveal view still legible, capture status text is readable, no modal/download blockage visible; saved screenshot artifact listed above.
  - Recording smoke via browser: PASS; JS-triggered record changed status to `Recording 10s…`, stopped after 10s, returned to reveal mode, and reported `Saved output.webm (6.82 MB)`.
- Known issues:
  - Right panel can still require scrolling in shorter screenshots; record button may be near the lower edge.
  - Actual MP4 generation/file-size validation is documented but not yet run in this tick.
  - Vite chunk-size warning remains non-blocking.
- Next slice: README/write-up draft with formulas, rules, reproduction, references, then final QA/artifact size checks.

## Tick 4 — README/write-up draft (2026-05-17 18:45)
- Slice: priority 4, README and write-up draft with formulas, rules, reproduction, references.
- Changed files: `README.md`, `writeup/writeup.md`, generated `dist/*` from build.
- Implemented:
  - Created `writeup/writeup.md` with required contest sections: title/teammates, description, technical aspects, reproduction, source/data map, limitations, and references.
  - Documented KAIST rule posture explicitly: browser WebGL/Three.js, no Blender rendering, no commercial/closed 3D tools, no external 3D assets, procedural source/config generation.
  - Added projection/inverse-projection formulas (`x = K[R|t]X`, `d_i = R^T K^-1 x_i`, `X_i = C + lambda_i d_i`) and mapped them to `backprojectNDC()`, text sampling, distorted room mesh, spheres, overlays, and reprojection metric.
  - Extended `README.md` with write-up pointer and final submission checklist for harness, console, representative PNG, MP4 limits, 3D content package, citations, and rule re-check.
- Verification:
  - `npm run harness`: PASS; Vite chunk-size warning only (`index-BjDGWRAV.js` > 500 kB).
  - Documentation sanity check: `README.md` 5,210 bytes / 105 lines; `writeup/writeup.md` 7,152 bytes / 147 lines.
  - Browser visual verification not rerun because this tick changed docs only, not visual behavior.
- Known issues:
  - Final MP4 export and file-size/duration validation are still documented but not yet executed.
  - Write-up is a draft and may need tightening to fit the final formatted 4-page limit with screenshots.
  - Vite chunk-size warning remains non-blocking.
- Next slice: final QA and artifact size checks — browser console check, representative/export artifact validation, and package-size sanity.

## Tick 5 — final QA and artifact size checks (2026-05-17 18:51)
- Slice: priority 5, final QA and artifact/package-size sanity without destructive cleanup.
- Changed files: `package.json`, `README.md`, new `scripts/final-qa.mjs`, generated `dist/*` from build, evidence screenshot `artifacts/perceptual-twin-final-qa-reveal-20260517-185142.png`, QA reports `artifacts/final-qa-20260517T095031Z.json` and `artifacts/final-qa-20260517T095148Z.json`.
- Implemented:
  - Added `npm run qa:submission` to generate timestamped JSON final-submission sanity reports under `artifacts/`.
  - QA report checks KAIST rule posture, required file presence, render duration/resolution settings, preserved PNG/WebM/MP4 artifact counts/sizes, and dist/source-bundle size estimates excluding `node_modules`/`.git`.
  - Updated README with the final QA command and source-map entry.
- Verification:
  - `npm run harness`: PASS; Vite chunk-size warning only (`index-BjDGWRAV.js` > 500 kB).
  - `npm run qa:submission`: PASS; latest report `artifacts/final-qa-20260517T095148Z.json` shows render config 1920x1080/10s within limits, `dist` 0.549 MB, source bundle excluding `node_modules`/`.git` 2.266 MB, 7 PNG artifacts with latest 0.235 MB under 5 MB, required files missing: none.
  - Browser smoke at `http://127.0.0.1:5173`: PASS; reference and reveal console checks reported no JS errors.
  - Browser visual inspection: reveal view renders correctly with readable HUD/labels/ghost overlay and usable controls; saved screenshot `artifacts/perceptual-twin-final-qa-reveal-20260517-185142.png` (244K).
- Known issues:
  - `output.mp4` is still not present; WebM-to-MP4 conversion is documented but must be run on the final chosen recording before submission.
  - Write-up remains a draft and should be tightened to fit the final formatted 4-page limit with selected screenshots.
  - Vite chunk-size warning remains non-blocking because Three.js is bundled.
  - `git status` could not be used because this working directory is not a Git repository.
- Next slice: if time remains, perform actual browser WebM export, convert to `output.mp4` with the README ffmpeg command, then run `ffprobe` and refresh `npm run qa:submission`.

## Tick 6 — browser export and MP4 validation (2026-05-17 18:58)
- Slice: actual browser WebM export, MP4 conversion, and submission-size validation.
- Changed files: `README.md`, preserved export artifacts `artifacts/perceptual-twin-browser-export-20260517T095647Z.webm` and `artifacts/perceptual-twin-browser-export-20260517T095647Z.mp4`, refreshed QA report `artifacts/final-qa-20260517T095745Z.json`, generated `dist/*` from build.
- Implemented:
  - Triggered the in-browser `10초 WebM 녹화` path from `http://127.0.0.1:5173`; the UI reported a saved WebM and returned to reveal/ghost mode.
  - Copied the browser-downloaded WebM into `artifacts/` with a unique timestamped name instead of overwriting previous evidence.
  - Ran ffmpeg conversion and fixed the README command after libx264 rejected an odd browser-capture width (`749x582`); the documented command now pads to even H.264 dimensions.
  - Produced timestamped MP4 evidence in `artifacts/` and refreshed final QA so it detects one WebM and one MP4 artifact.
- Verification:
  - `npm run harness`: PASS; Vite chunk-size warning only (`index-BjDGWRAV.js` > 500 kB).
  - Browser console after recording: PASS; no JavaScript errors. Only Vite debug messages and a Three.js soft-shadow deprecation warning.
  - ffmpeg/ffprobe: PASS; MP4 `artifacts/perceptual-twin-browser-export-20260517T095647Z.mp4` is 750x582, 60 fps, 6.733333s, 1,914,957 bytes (~1.826 MB), under the KAIST <=10s and <=50MB limits.
  - `npm run qa:submission`: PASS; latest report `artifacts/final-qa-20260517T095745Z.json` shows `mp4ExportPresent: true`, `mp4Count: 1`, `webmCount: 1`, `dist` 0.549 MB, source bundle excluding `node_modules`/`.git` 7.232 MB.
- Known issues:
  - The browser tool viewport recorded 750x582 rather than the final target 1920x1080; it is within contest limits, but a final human export should maximize the browser viewport before recording the official `output.mp4`.
  - Browser MediaRecorder produced a 6.73s MP4 after frame-rate normalization even though the UI wall-clock timer stopped at 10s; still contest-compliant (`<=10s`) but not a full 10s showcase.
  - Vite chunk-size warning remains non-blocking because Three.js is bundled.
- Next slice: if time remains, record one higher-resolution official export from a maximized browser/Edge window, then rerun ffprobe and `npm run qa:submission`; otherwise tighten the 4-page write-up around final screenshots.

