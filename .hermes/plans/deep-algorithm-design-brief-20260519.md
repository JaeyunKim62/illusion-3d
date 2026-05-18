# Deep Algorithm Design Brief — Asset Search, 4+ View Lenticular, 3-View

> Purpose: read this after `/new` and immediately proceed into deep algorithm design. This is not the final algorithm plan. It is the compact problem framing, constraints, candidate directions, and expected deliverables for the next long design/implementation session.

## Current repo state to preserve

Branch at time of writing: `algorithm-exploration-20260518`.

The current viewer is a stable 2-view fallback demo. Do not continue polishing row banding unless explicitly asked.

Current baseline facts:

- One physical `THREE.Points` object.
- One shared `THREE.BufferGeometry`.
- No projection-only points.
- No hidden image planes/billboards.
- No texture swap.
- No view-dependent opacity gate.
- Current row materialization: `quantile_max` / sorted midpoint quantile pairing.
- Current color: endpoint attributes `frontColor` / `sideColor` with `cosine_s1` directional color.
- Known limitation: horizontal row banding is accepted as a structural footprint of row-shared 2-view construction.
- Current visual tuning:
  - `POINT_SCALE_Y = 1.28`
  - `VIEW_HALF_HEIGHT = 1.54`
  - `SUB_ROW_JITTER_SCALE = 0.42`
  - `POINT_SIZE = 2.65`
  - `POINT_ALPHA = 0.68`
  - `POINT_SIZE_JITTER = 0.10`
- Latest checked commands before this brief:
  - `npm run harness:algorithm:require-production` PASS
  - `npm run harness` PASS
  - `npm run build` PASS

Recent relevant docs:

- `CURRENT_HANDOFF.md`
- `README.md`
- `.hermes/plans/next-illusion-concepts-20260519.md`
- `artifacts/algorithm-exploration/final-one-hour-algorithm-recommendation-20260518.md`

## Overall next-session goal

Design deep algorithms for three directions:

1. Asset search / asset compatibility scoring.
2. 2-view base plus lenticular extension with 4 or more apparent views/frames.
3. True or approximate 3-view illusion: front/right/top or equivalent three canonical projections.

The next session should not jump directly into visual polish. First produce algorithm designs with equations, data structures, objective functions, feasibility tests, failure gates, and harness plans. Implementation can start only after the algorithms are clear enough to test.

## Shared guardrails for all three directions

Unless a new concept explicitly relaxes the rules, preserve the current contest-style invariant:

- Prefer one physical point set.
- Prefer one shared geometry.
- Keep point identity stable.
- Do not hide extra image planes.
- Do not swap textures by camera view.
- Do not use alpha=0 visibility gates to fake readings.
- If directional material/color is used, document it as material response, not geometry swap.
- If any direction needs relaxed rules, state that explicitly before implementation.

Each direction needs:

- A feasibility metric before browser rendering.
- A small synthetic/toy test before real assets.
- A real-asset smoke test.
- A contact sheet or captured evidence.
- A blunt failure/reject criterion.

---

# Direction 1 — Asset Search / Compatibility Scoring

## Problem

The algorithm can only produce strong illusions when the target assets are compatible with the geometry constraints. Bad assets cause row mismatch, missing coverage, unstable density, color conflict, and unreadable side/top views. Asset search should become the upstream filter for 2-view, 4+ lenticular, and 3-view experiments.

## Algorithm design target

Build an offline scorer that takes a pool of candidate images or generated masks and ranks:

- 2-view pairs: `(A_front, B_side)`.
- 3-view triples: `(A_front, B_side, C_top)`.
- Lenticular frame sets: `(F_0, F_1, ..., F_{n-1})`, `n >= 4`.

The scorer should not require opening the browser. It should output a ranked report and contact sheets for the top candidates.

## Core mask representation

For each image `I`:

```text
M_I(x,y) ∈ {0,1}
RGB_I(x,y) ∈ [0,1]^3
Rows_I[y] = { x | M_I(x,y)=1 }
Cols_I[x] = { y | M_I(x,y)=1 }
```

Also compute:

```text
activeRows(I)
activeCols(I)
area(I)
bbox(I)
centerOfMass(I)
rowCount_I[y] = |Rows_I[y]|
colCount_I[x] = |Cols_I[x]|
edgeComplexity(I)
colorStats(I)
```

## 2-view pair metrics

For front `A(x,y)` and side `B(z,y)`:

```text
rowOverlap = |activeRows(A) ∩ activeRows(B)| / |activeRows(A) ∪ activeRows(B)|
frontOnlyRows = |activeRows(A) - activeRows(B)|
sideOnlyRows = |activeRows(B) - activeRows(A)|
matchedRows = activeRows(A) ∩ activeRows(B)
```

For each matched row `y`:

```text
N_y = max(|Rows_A[y]|, |Rows_B[y]|)
rowImbalance_y = | |Rows_A[y]| - |Rows_B[y]| | / max(|Rows_A[y]|, |Rows_B[y]|)
```

Aggregate:

```text
pointCountEstimate = Σ_y∈matchedRows N_y
rowDensitySpread = percentile95(N_y) / max(1, percentile05(N_y))
coverageFront = Σ_y∈matchedRows |Rows_A[y]| / area(A)
coverageSide = Σ_y∈matchedRows |Rows_B[y]| / area(B)
shapeAspectCompatibility = penalty(abs(aspect(A) - aspect(B)))
verticalCOMPenalty = |cy(A) - cy(B)|
```

Color conflict estimate for directional color:

```text
colorConflict = mean_y,k || RGB_A(x_k,y) - RGB_B(z_k,y) ||
luminanceConflict = mean_y,k |Y_A(x_k,y) - Y_B(z_k,y)|
```

Suggested 2-view score:

```text
score2 =
  + 2.0 * rowOverlap
  + 1.5 * min(coverageFront, coverageSide)
  - 1.0 * rowDensitySpreadPenalty
  - 0.8 * verticalCOMPenalty
  - 0.6 * colorConflict
  - 0.5 * edgeComplexityPenalty
```

## 3-view triple metrics

Given front `A(x,y)`, side `B(z,y)`, top `C(x,z)`.

Front/side generate possible top support:

```text
S_top = ⋃_y Rows_A[y] × Rows_B[y]
```

Top feasibility:

```text
topRecall = |C ∩ S_top| / |C|
topPrecisionProxy = |C ∩ S_top| / |S_top sampled or bounded|
impossibleTopPixels = |C - S_top|
```

For each top pixel `(x,z) ∈ C`, estimate whether there exists some `y` such that:

```text
x ∈ Rows_A[y] and z ∈ Rows_B[y]
```

If not, the top pixel cannot be represented without adding points that create front/side noise.

Suggested triple score:

```text
score3 =
  + 1.5 * score2(A,B)
  + 2.5 * topRecall
  - 1.5 * impossibleTopRatio
  - 1.0 * topNoiseProxy
  - 0.5 * pointExplosionPenalty
```

## Lenticular frame-set metrics

For frames `F_i`, `i=0..n-1`:

Measure:

```text
commonSupport = intersection or soft-overlap of masks
unionSupport = union of masks
frameIoUAdjacent = IoU(F_i, F_{i+1})
centerDrift = ||COM(F_i)-COM(F_{i+1})||
areaDrift = |area(F_i)-area(F_{i+1})| / max(area)
edgeDelta = edge change between adjacent frames
```

Good lenticular frame sets should have:

- Related silhouettes.
- Limited center drift.
- Moderate internal/color change.
- Simple edges.
- Stable vertical/horizontal extents.

Suggested frame-set score:

```text
scoreL =
  + mean(adjacentIoU)
  + shapeContinuity
  + colorSeparability
  - centerDriftPenalty
  - areaDriftPenalty
  - highFrequencyEdgePenalty
```

## Expected outputs

Implement/design toward:

```text
scripts/asset-search.mjs or scripts/asset-search.py
artifacts/asset-search/report.json
artifacts/asset-search/top-pairs.md
artifacts/asset-search/contact-sheet.png
```

Report should include:

- ranked 2-view pairs
- ranked 3-view triples
- ranked lenticular frame sets
- raw metrics
- recommended candidates for browser experiments

## Failure gates

Reject an asset candidate if:

- row overlap is low for 2-view.
- coverage of either endpoint is too low.
- 3-view top recall is poor.
- lenticular adjacent frame continuity is poor.
- score looks good numerically but contact sheet shows ambiguous/unrecognizable silhouettes.

---

# Direction 2 — 2-View Base + 4+ View Lenticular

## Problem

Create a stronger motion/angle-dependent illusion than the static 2-view demo. The target is 4 or more apparent views/frames from a single shared object when the camera moves left/right or up/down.

Examples:

- eyes blink across 4 frames
- character changes pose
- logo morphs
- object opens/closes
- color/detail changes across camera movement

## Key design choice

There are two broad mechanisms:

1. Directional material/multi-lobe color basis.
2. Geometric parallax frame encoding.

The deep design should compare both, but first implementation should likely start with multi-lobe directional material because it is closer to the current `cosine_s1` shader.

## Option A — Multi-lobe directional color/material basis

Current 2-view shader:

```text
c(view) = wF(theta) * frontColor + wR(theta) * sideColor
wF = cos(theta)/(cos(theta)+sin(theta))
wR = sin(theta)/(cos(theta)+sin(theta))
```

Extend to `n >= 4` lobes:

```text
theta_i = target angle for frame i
raw_i(theta) = max(0, cos(theta - theta_i))^p
w_i(theta) = raw_i(theta) / Σ_j raw_j(theta)
c(theta) = Σ_i w_i(theta) * color_i
```

For horizontal camera movement, `theta` can be the camera angle around the object or a normalized view coordinate:

```text
u = clamp((camera.x - x_min)/(x_max-x_min), 0, 1)
raw_i(u) = exp(-((u-u_i)^2)/(2σ^2))
w_i(u) = raw_i(u)/Σ raw_j(u)
```

Each point stores:

```text
color0, color1, color2, color3, ...
```

Potential geometry choices:

- Use current 2-view geometry and encode frame changes mostly in color/detail.
- Build a common support geometry from all frames, then assign per-frame colors where active/inactive.
- Use alpha-like brightness carefully but avoid view-opacity gate semantics. If inactive pixels are represented, document as low luminance material, not hidden geometry.

Risks:

- If frames differ too much in silhouette, color-only change will not read.
- If lobe transition is too sharp, it looks like a texture swap.
- If lobe transition is too broad, frames blend into mush.

Harness metrics:

```text
frameColorError_i
frameSilhouetteError_i
transitionSmoothness
maxAdjacentFrameStep
lobeLeakage_i_to_j
```

Browser evidence:

- capture fixed angles `theta_0...theta_3`
- contact sheet
- sweep video/contact strip
- runtime QA:
  - `viewCount >= 4`
  - `materialPolicy=multi_lobe_directional_color`
  - `geometryCount=1`
  - `textureSwap=false`

## Option B — Geometric parallax frame encoding

Goal: small camera translation changes projected positions enough that different frames align.

Camera projection for a point `(x,y,z)` under small horizontal camera shift can be approximated as:

```text
screen_x ≈ x + parallax_scale * z * camera_offset
screen_y ≈ y
```

For target frame `i` at camera offset `u_i`, point should project to frame coordinates:

```text
x_i ≈ x + s * z * u_i
```

For two or more frames, solve for `x,z` from desired projected positions:

```text
x_i = x + s z u_i
```

With two frames, exact fit is possible for paired pixels:

```text
z = (x_1 - x_0) / (s (u_1-u_0))
x = x_0 - s z u_0
```

With 4+ frames, exact fit is over-constrained unless the pixel trajectories are approximately linear across frames. Therefore assets should be coherent animations with smooth motion.

Potential algorithm:

1. Extract frame masks `F_i`.
2. Establish correspondences across frames using optical-flow-like matching or sorted row quantiles.
3. Fit per-track linear trajectory in screen x/y as a function of camera offset.
4. Convert track parameters into 3D point positions.
5. Render and measure frame error at each offset.

For vertical movement, use `y` parallax instead:

```text
screen_y ≈ y + s * z * camera_offset_y
```

Risks:

- Hard correspondence problem.
- Occlusion and many-to-one conflicts.
- Point depth may explode for large motion.
- Can look like layered billboards if not constrained.

Harness metrics:

```text
trajectoryFitError
maxDepth
depthSpread
frameCoverage_i
frameNoise_i
trackDropRate
```

## Recommended lenticular first spike

Start with Option A:

```text
4-frame multi-lobe directional color over common/support geometry
```

Then, if that looks too weak, design Option B as a second-stage parallax solver.

## Expected outputs

```text
scripts/lenticular-lobe-harness.mjs
artifacts/lenticular-4view/report.json
artifacts/lenticular-4view/contact-sheet.png
artifacts/lenticular-4view/sweep.webm or png strip
```

## Failure gates

Reject if:

- frames are only distinguishable by labels.
- transition looks like a texture swap.
- more than one point cloud or hidden plane is required.
- frame leakage makes all views unreadable.
- browser evidence does not show at least 4 distinct readings.

---

# Direction 3 — 3-View Illusion

## Problem

Create one point set that reads as three images from three canonical directions, e.g.:

```text
front +Z: A(x,y)
right +X: B(z,y)
top +Y or top-like view: C(x,z)
```

This is much harder than 2-view because the third view constrains the joint `(x,z)` relationship, not just row-wise `x` and `z` marginals.

## Current 2-view construction

For each row `y`:

```text
X_y = {x | A(x,y)=1}
Z_y = {z | B(z,y)=1}
N_y = max(|X_y|, |Z_y|)
p_k = (x_k, y, z_k)
```

This guarantees front/right row coverage but does not care what top projection `(x,z)` looks like.

## 3-view constraint

Top target requires:

```text
(x,z) ∈ C
```

for points that should contribute to top image.

But front/right require the same point to satisfy:

```text
x ∈ X_y
z ∈ Z_y
```

Therefore each point must lie in:

```text
P_allowed = { (x,y,z) | A(x,y)=1 and B(z,y)=1 }
```

and its top projection contributes to:

```text
Top(P) = { (x,z) | ∃ y: (x,y,z) ∈ P }
```

The key feasibility question:

```text
How much of C is inside Top(P_allowed)?
```

## Algorithm stage A — Feasibility checker

Compute:

```text
S_top = ⋃_y X_y × Z_y
```

Metrics:

```text
topRecall = |C ∩ S_top| / |C|
impossibleTopRatio = |C - S_top| / |C|
possibleNoiseProxy = |S_top - C| / |S_top|
frontCoveragePotential
rightCoveragePotential
pointCountLowerBound
pointCountUpperBound
```

Also report per-top-pixel support count:

```text
supportCount(x,z) = |{ y | x ∈ X_y and z ∈ Z_y }|
```

High support count means easier to choose a `y` without harming front/right. Low support count means fragile.

Failure gate:

```text
if topRecall < threshold, reject assets before rendering.
```

## Algorithm stage B — Greedy voxel subset solver

Candidate voxels:

```text
V = { (x,y,z) | A(x,y)=1 and B(z,y)=1 }
```

Each voxel covers:

```text
front pixel (x,y)
right pixel (z,y)
top pixel (x,z)
```

Objective:

```text
maximize
  wF * coveredFront
+ wR * coveredRight
+ wT * coveredTop
- nF * frontNoise
- nR * rightNoise
- nT * topNoise
- d  * densityPenalty
```

But if `V` only includes front/right active pixels, front/right noise is zero by construction. Top noise appears when `(x,z) ∉ C`.

Greedy approach:

1. Start with empty point set `P`.
2. Prioritize candidate voxels where `(x,z) ∈ C`.
3. Add voxels that cover uncovered top pixels while also covering useful front/right pixels.
4. Fill remaining front/right coverage using quantile row materialization, but penalize top noise.
5. Optionally prune points that add top noise with low front/right benefit.

Scoring for a candidate voxel `v`:

```text
gain(v) =
  wF * newFront(v)
+ wR * newRight(v)
+ wT * newTop(v)
- nT * topNoise(v)
- densityPenalty(localDensity)
```

## Algorithm stage C — Row-wise top-constrained matching

For each `y`, choose pairings between `X_y` and `Z_y` that make top projection closer to `C`.

Instead of current quantile pair:

```text
x_k paired with z_k by sorted midpoint quantile
```

solve row assignment:

```text
minimize Σ cost(x,z)
where cost(x,z) =
  - topReward(x,z)
  + smoothnessPenalty
  + multiplicityPenalty
```

where:

```text
topReward(x,z) = 1 if C(x,z)=1 else -λ
```

This can be approximate:

- greedy matching
- Hungarian assignment for small rows
- sampled candidate pairs for wide rows
- quantile initialization followed by local swaps

This stage is likely more stable than full greedy voxel selection because it preserves 2-view row coverage.

## Recommended 3-view first spike

Order:

1. Implement feasibility checker only.
2. Test current real assets and simple generated assets.
3. Generate/co-design toy assets that pass top feasibility.
4. Implement row-wise top-constrained matching.
5. Only then add browser top-view mode.

Do not begin with arbitrary three character images. That will likely fail and waste time.

## Expected outputs

```text
scripts/three-view-feasibility.mjs
scripts/three-view-solver.mjs
artifacts/three-view/feasibility-report.json
artifacts/three-view/toy-contact-sheet.png
artifacts/three-view/solver-report.json
```

Browser QA fields if implemented:

```text
projectionCount = 3
frontCoverage
rightCoverage
topCoverage
topNoiseRatio
projectionOnlyPointCount = 0
sharedGeometry = true
rowPolicy or solverPolicy
```

## Failure gates

Reject an asset triple if:

- `topRecall` is low.
- top support requires too many points that create top noise.
- front/right readability collapses.
- point count explodes.
- the third view only works by adding projection-only points or hidden geometry.

---

# Recommended 10-hour deep design / implementation sequence

## Phase 0 — Entry checks, 15 min

- Confirm branch/worktree.
- Confirm clean git status.
- Run:
  - `npm run harness:algorithm:require-production`
  - `npm run harness`
- Create a new branch or worktree for the selected 10-hour exploration.

## Phase 1 — Asset search foundation, 1.5–2h

Design and implement the minimum scorer that can evaluate current available assets and toy/generated masks.

Deliver:

- ranked 2-view pairs
- ranked possible 3-view triples
- ranked lenticular frame sets if frame assets exist
- JSON report
- contact sheet or markdown table

## Phase 2 — 3-view feasibility, 2–2.5h

Design and implement support-envelope feasibility:

```text
S_top = ⋃_y X_y × Z_y
```

Deliver:

- report for current assets
- report for generated toy assets
- recommendation whether to continue 3-view or stop at feasibility

## Phase 3 — 4+ view lenticular lobe design/prototype, 2.5–3h

Design and prototype multi-lobe directional material first.

Deliver:

- 4 target view/frame basis
- weight function
- contact sheet across angles
- browser or offline render evidence if possible

## Phase 4 — Compare and choose, 1–1.5h

Write a decision report:

- Which direction has highest visual upside?
- Which has lowest implementation risk?
- Which assets are needed?
- What is the next concrete implementation plan?

Expected final artifact:

```text
artifacts/deep-algorithm-design-20260519/final-recommendation.md
```

## Success criteria for the 10-hour session

Minimum success:

- asset scorer exists
- 3-view feasibility is quantified
- 4+ view lenticular algorithm is specified with a harness plan

Good success:

- asset scorer produces useful candidates
- 3-view toy case passes feasibility
- 4+ view contact sheet shows distinguishable frames

Great success:

- 4+ view prototype is visually promising in browser
- 3-view toy solver renders front/right/top recognizably
- final report chooses one direction with evidence

## What not to do first

- Do not spend hours polishing row banding.
- Do not attempt arbitrary 3-view assets before feasibility.
- Do not implement hidden billboards or texture swaps and call it a point-cloud illusion.
- Do not optimize browser visuals before metrics/contact sheets exist.
- Do not overwrite the stable 2-view fallback without a branch/worktree.
