# What We See Is Not What Exists: A Perceptual Twin Room

Browser/WebGL implementation for the KAIST 3D Rendering Contest. The scene is procedural: a reference camera defines the intended 2D percept, then text pieces and room vertices are back-projected into 3D at different depths. From the reference view the viewer reads `WHAT WE SEE` and a normal-looking room; from the reveal view the physical geometry is visibly distorted.

## KAIST rule posture

- Renderer: Three.js/WebGL in the browser.
- No Blender rendering.
- No commercial or closed 3D tools.
- No external 3D assets, meshes, scans, or textures.
- Geometry, checker materials, labels, and text masks are generated in source code from reproducible parameters in `scene_config.json`.
- Required submission targets from the proposal: representative PNG <= 1920x1080 and <= 5MB; MP4 <= 10s, <= 1920x1080, <= 50MB; one 3D content package <= 100MB; source/data and write-up included.

## Run and verify

```bash
npm install
npm run dev
# open http://127.0.0.1:5173
npm run harness
```

`npm run harness` currently runs TypeScript checking and a Vite production build. A Vite chunk-size warning can appear because Three.js is bundled; it is not a build failure.

For final submission sanity checks, run:

```bash
npm run qa:submission
```

This writes a timestamped JSON report under `artifacts/` with rule posture, required-file presence, preserved artifact sizes, render duration/resolution settings, and content-bundle size estimates. It complements, but does not replace, the browser console/visual check and actual MP4 export validation.

## Viewer controls

- `10초 영상 재생`: plays the full 10-second narrative path.
- `기준 시점`: clean reference camera view where the perceptual target should read normally.
- `왜곡 reveal`: side/reveal view with reduced ghost overlay by default.
- `자유 Orbit`: inspect physical distortion interactively.
- `Overlay`: cycles `Off -> Ghost -> Rays -> All` to avoid ray/frustum clutter in judging views.
- `PNG 캡처`: downloads `representative.png` from the current canvas.
- `10초 WebM 녹화`: starts the timeline from t=0, records the canvas at `scene_config.json` fps, and stops after `durationSec` (10s).

## Capture/export flow

1. Open the app in Chromium/Edge at `http://127.0.0.1:5173`.
2. Press `기준 시점` or `왜곡 reveal`, then `PNG 캡처` to save a representative image.
3. Press `10초 WebM 녹화`; leave the tab focused until the browser downloads `output.webm`.
4. Convert WebM to contest MP4 with ffmpeg:

```bash
ffmpeg -y -i output.webm \
  -t 10 \
  -vf "fps=60,scale='min(1920,iw)':-2,pad=ceil(iw/2)*2:ceil(ih/2)*2,format=yuv420p" \
  -c:v libx264 -preset slow -crf 20 -movflags +faststart \
  output.mp4
```

The `pad=ceil(iw/2)*2:ceil(ih/2)*2` step keeps H.264 dimensions even if the browser canvas was recorded at an odd CSS pixel width such as 749 px.

5. Check the output constraints:

```bash
ffprobe -v error -show_entries format=duration,size -of default=noprint_wrappers=1 output.mp4
```

If the MP4 is over 50MB, raise CRF, e.g. `-crf 23`. If browser MediaRecorder is unavailable, use Chromium/Edge or capture frames with a separate screen recorder that preserves the browser/WebGL output.

## Technical summary

Reference-camera projection follows the course camera model:

```text
x = K [R | t] X = P X
```

This project uses the inverse direction for procedural generation. For each target NDC/image point `x_i`, it constructs the reference-camera ray and places a physical point at depth `lambda_i`:

```text
d_i = R^T K^-1 x_i
X_i = C + lambda_i d_i
```

In Three.js this is implemented with `Vector3.unproject(camera)` in `backprojectNDC()`. The code also projects generated points back to the reference camera and reports mean reprojection error in pixels.

## Write-up draft

A contest write-up draft is available at `writeup/writeup.md`. It includes the required sections for title/teammates, description, technical aspects, reproduction steps, limitations, and references. Keep it to four A4 pages or fewer when formatting for final submission.

## Source map

- `src/main.ts`: renderer setup, inverse projection helpers, procedural text/room/sphere generation, overlays, timeline, PNG/WebM capture.
- `src/contestRules.ts`: durable KAIST rule summary displayed in the app.
- `src/styles.css`: browser UI and capture-status styling.
- `scripts/final-qa.mjs`: timestamped final-submission sanity report for artifact/file/bundle size checks.
- `scene_config.json`: reproducible camera, text, room, object, and render parameters.
- `project_proposal.md`: full Korean project specification and write-up outline.
- `writeup/writeup.md`: submission write-up draft with formulas, rule posture, reproduction, limitations, and references.
- `artifacts/`: preserved browser evidence screenshots from implementation ticks.

## Final submission checklist

- [ ] Run `npm run harness` and confirm build passes.
- [ ] Browser console has no JavaScript errors in reference/reveal views.
- [ ] Export `representative.png` at <=1920x1080 and <=5MB.
- [ ] Export/convert `output.mp4` at <=10s, <=1920x1080, and <=50MB.
- [ ] Package one browser 3D content bundle under 100MB.
- [ ] Include source/data and cite Three.js, Vite/TypeScript, Canvas API usage, and contest rules in the final write-up.
- [ ] Re-check no external 3D assets, no Blender rendering, and no commercial/closed 3D tools are introduced.

## Dependencies and references

- Three.js / WebGL for browser rendering and OrbitControls.
- Vite and TypeScript for local development/build tooling.
- HTML Canvas 2D API for procedural text mask sampling and label sprites.
- ffmpeg is optional for local WebM-to-MP4 conversion; it is not part of the browser 3D content.
- KAIST 3D Rendering Contest rules summarized in `project_proposal.md` and `src/contestRules.ts`.
