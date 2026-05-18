# Next Illusion Concept Options

> Scope: new concepts after freezing the current 2-view lenticular point-cloud viewer as a stable baseline. Do not mutate the current production demo until a concept wins a spike.

## Current baseline to preserve

- One shared physical point set.
- Front/right 2-view quantile row materialization.
- Directional endpoint color.
- Known limitation: row banding is accepted as a structural footprint for this baseline.
- Current best visual tuning: `POINT_SCALE_Y=1.28`, `VIEW_HALF_HEIGHT=1.54`, `SUB_ROW_JITTER_SCALE=0.42`, `POINT_SIZE=2.65`, `POINT_ALPHA=0.68`, `POINT_SIZE_JITTER=0.10`.

## Candidate A — Designed 3-view support illusion

**Idea:** Add a top/third image only when assets are co-designed to fit the front/side support envelope.

**Why it may be worth it:** Highest technical upside if successful: one point cloud, three recognizable orthographic readings.

**Asset need:** Must choose or generate three silhouettes with compatible supports. Arbitrary third images are likely infeasible.

**Spike plan:**
1. Build a feasibility checker for `front A(x,y)`, `side B(z,y)`, `top C(x,z)`.
2. Report top target coverage inside `S = union_y X_y × Z_y` before rendering.
3. Try simple co-designed geometric/icon assets first, not arbitrary characters.

**Reject if:** top recall is poor or front/right recognizability collapses.

## Candidate B — Vertical/horizontal lenticular motion from one view

**Idea:** From one viewing direction, small camera movement left/right or up/down changes the visible image, like a lenticular card.

**Why it may be worth it:** More immediately legible to viewers than static multi-orthographic images. Motion itself becomes the magic.

**Asset need:** A short sequence or 2-4 related frames: expression change, character pose, logo morph, blinking eyes, opening object.

**Possible mechanisms:**
- Layered depth/color basis where parallax changes projected samples.
- Directional shader color basis with multiple lobes.
- Carefully constrained view-dependent material response, but no hidden billboards or opacity gates if preserving current contest invariant style.

**Spike plan:**
1. Define allowed rule boundary: directional color only vs geometric parallax.
2. Prototype with 2 frames first: left view image A, right-offset view image B.
3. Add browser capture path that sweeps camera horizontally and saves a contact sheet.

**Reject if:** it reads as a texture swap, billboard trick, or only works from a single hidden camera.

## Candidate C — Motion illusion / animated drawing from camera movement

**Idea:** The image appears to animate as the camera moves: walking, blinking, rotating icon, opening/closing mouth.

**Why it may be worth it:** Strong presentation value and easy to understand in a 10s video.

**Asset need:** Coherent animation frames with simple silhouettes and stable vertical extents.

**Spike plan:**
1. Start with 3 frames, not many.
2. Use a known camera path as the independent variable.
3. Score frame recognizability at sampled camera positions.

**Risk:** Multi-frame support constraints are much harder than 2-view; may need a different representation than the current row-pair cloud.

## Candidate D — Asset-search pipeline for the current 2-view algorithm

**Idea:** Keep the stable algorithm, but find better front/side asset pairs that naturally reduce row mismatch and improve recognizability.

**Why it may be worth it:** Lowest engineering risk; quality may improve more from better assets than more shader tuning.

**Asset need:** Batch of simple, high-contrast silhouettes/icons/characters.

**Spike plan:**
1. Add an offline scorer for pairs: active-row overlap, side-only rows, point count, row density spread, color conflict.
2. Generate a ranked list before opening the browser.
3. Browser-test only top candidates.

**Reject if:** asset search does not outperform the current pair on both recognizability and row-balance metrics.

## Candidate E — Hybrid physical sculpture + projection-style reveal

**Idea:** Keep one point set but improve the reveal with helper non-point diagnostics or lighting/camera choreography while preserving the two canonical readings.

**Why it may be worth it:** Safer presentation upgrade if new algorithms become too risky.

**Asset need:** None or minimal.

**Spike plan:**
1. Create a new reveal-only branch.
2. Improve camera path, depth cues, and labels.
3. Keep canonical front/right images unchanged.

**Reject if:** it feels like presentation polish rather than a new concept.

## Recommended order

1. Candidate D: asset-search scorer — fastest way to discover better material for any direction.
2. Candidate B: one-direction lenticular motion — best balance of novelty and feasibility.
3. Candidate A: 3-view — highest upside but requires co-designed assets and strict feasibility checks.
4. Candidate C: animated motion — attempt after B proves the mechanism.
5. Candidate E: presentation fallback — only near submission if needed.

## Guardrails for all new spikes

- Use a new branch/worktree for each concept.
- Keep the current 2-view viewer as stable fallback.
- Before implementation, define the exact rule boundary: allowed directional material response, forbidden hidden image planes, forbidden texture swaps, and whether multiple point sets are allowed for the new concept.
- Add a feasibility/harness script before browser polish.
- Save evidence under a concept-specific artifact directory.
