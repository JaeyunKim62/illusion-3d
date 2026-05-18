# Iterative deepening log — 2026-05-18

This file is appended by the one-hour algorithm exploration runner.

---

## Iteration 1 — row OT materialization + 3-view feasibility deepening

Scope guard:
- Branch checked by tool: `algorithm-exploration-20260518`.
- Production files not modified. New/changed files are only under `artifacts/.hermes/` and `artifacts/algorithm-exploration/`.
- Read required prior outputs: `deep-algorithm-proposal-20260518.md`, `verification-plan-20260518.md`, `algorithm_exploration_probe_20260518.json`, and this iterative log.

Iteration-specific files:
- `artifacts/.hermes/iteration1_real_image_row_probe_20260518.py`
- `artifacts/algorithm-exploration/iteration-1-real-image-row-probe-20260518.json`
- `artifacts/algorithm-exploration/iteration-1-row-ot-and-feasibility-deepening-20260518.md`

### A. Critique of previous conclusion

The previous proposal is directionally right, but several parts were too shallow:

1. Row OT was named but discrete materialization was underspecified. A renderer needs integer point counts `n_ij`, not fractional transport `T_ij`. The missing constraints are:

```text
n_ij ∈ Z_>=0
Σ_ij n_ij = N_y
covered_x_i = 1[Σ_j n_ij > 0]
covered_z_j = 1[Σ_i n_ij > 0]
penalize multiplicity imbalance: Var(Σ_j n_ij), Var(Σ_i n_ij), max multiplicity
```

2. 3-view exact feasibility used the correct visual-hull condition `π(H)=A/B/C`, but did not expose the row-graph certificate enough. For each row:

```text
G_y=(X_y,Z_y,E_y), E_y={(x,z): A(x,y)=1 ∧ B(z,y)=1 ∧ C(x,z)=1}
∀(x,y)∈A: degree_G_y(x)>0
∀(z,y)∈B: degree_G_y(z)>0
∀(x,z)∈C: ∃y such that x∈X_y and z∈Z_y
```

3. Exact feasibility is not enough. Even if `H` projects exactly, `|H|` or row edge density can explode and make reveal look like a dense block. Need a density certificate: rowEdgeCount p50/p95/max, voxel budget estimate, sampled multiplicity histogram.

4. Directional color lobe analysis had endpoint fit but no no-pop regularizer. Missing metrics:

```text
L_pop = max_θ mean_i ||c_i(θ+Δ)-c_i(θ)||
L_accel = mean_{θ,i} ||c_i(θ+Δ)-2c_i(θ)+c_i(θ-Δ)||
L_leak = wrong-lobe weight at canonical views
```

5. The previous probe was synthetic only. That made row color conclusions weak because actual alpha masks, antialiasing, object scale mismatch, and real color distributions were not tested.

### B. New concrete progress: actual reference-image row probe

I added and ran a throwaway real-image proxy probe. It uses actual reference images with alpha masks:
- `goose.png + nubzuki.png`
- `goose.png + cake.png`

Policies:
- `min_quantile`
- `current_modulo`
- `quantile_max`
- `color_aware_local`  (quantile anchor plus local color search; not full OT)

Important limitation: this is still a proxy. It resizes/normalizes alpha masks and does not use the production renderer or exact `src/main.ts` extraction.

### C. Results

For `goose+nubzuki`:

```text
current_modulo:    points=1278, front_iou=0.509479, side_iou=0.477541,
                   conflict_mean=0.409435, conflict_p95=0.775770,
                   fixed_blend_rmse_proxy=0.204718
quantile_max:      same point count and IoU,
                   conflict_mean=0.377321, conflict_p95=0.618896,
                   fixed_blend_rmse_proxy=0.188661
color_aware_local: front_iou=0.509479, side_iou=0.475965,
                   conflict_mean=0.374984, conflict_p95=0.597886,
                   fixed_blend_rmse_proxy=0.187492
```

Tool-computed improvement vs current modulo:

```text
quantile_max conflict mean: 7.84% lower
quantile_max conflict p95: 20.22% lower
color_aware conflict mean: 8.41% lower
color_aware conflict p95: 22.93% lower
color_aware side IoU delta: -0.001576 absolute
```

For `goose+cake`:

```text
current_modulo:    points=3468, front_iou=0.938389, side_iou=0.673215,
                   conflict_mean=0.466686, conflict_p95=0.786653
quantile_max:      same IoU, conflict_mean=0.469797, conflict_p95=0.798984
color_aware_local: side_iou=0.673021, conflict_mean=0.469671, conflict_p95=0.798984
```

Tool-computed change vs current modulo:

```text
quantile_max conflict mean: 0.67% worse
color_aware conflict mean: 0.64% worse
side IoU delta for color-aware: -0.000194 absolute
```

### D. Updated recommendation from iteration 1

Do not jump straight from current modulo to full Sinkhorn/OT. The next implementation spike should be staged:

1. Reproduce current modulo in an experiment harness.
2. Test `quantile_max` materialization as a minimal replacement:

```text
N_y=max(|X_y|,|Z_y|)
x_k=Q_X((k+0.5)/N_y)
z_k=Q_Z((k+0.5)/N_y)
```

3. Then test local color-aware quantile only if it improves multiple real image pairs:

```text
z_k = argmin_{z in window(Q_Z(k))}
      λ_pos |rank(z)-rank(Q_Z(k))|/window
    + λ_color ||RGB_A(x_k,y)-RGB_B(z,y)||
    + λ_reuse reusePenalty(z)
```

4. Full OT/Sinkhorn is only justified if the simpler materializations cannot capture the benefit.

3-view gate should become a row-graph + density certificate, not only IoU:

```json
{
  "exactVisualHullPass": false,
  "frontIsolatedPixelRatio": 0.0,
  "sideIsolatedPixelRatio": 0.0,
  "unsupportedTopPixelRatio": 0.0,
  "rowEdgeCountP50": 0,
  "rowEdgeCountP95": 0,
  "voxelBudgetEstimate": 0
}
```

Directional color basis should compare normalized cosine lobes, angular Gaussian, softmax logits, and SH order 1/2 with endpoint error + leakage + max frame color jump + acceleration.

### E. Open questions for iteration 2

1. Mirror `src/main.ts` extraction more closely in throwaway code; current real-image probe is not production-equivalent.
2. Generate visual/contact-sheet evidence for row pairing; metrics may hide visible artifacts.
3. Add row banding/multiplicity heatmap metrics: duplicate entropy, duplicate Gini, per-row multiplicity p95/max.
4. Run actual top-candidate graph probe using `phoenix.png`/`kumdori.png`, not only synthetic 3-view masks.
5. Run directional basis sweep with `L_pop`, `L_accel`, endpoint leakage, not just endpoint RMSE.
6. Formalize angular morph decision rule: if target support differs from canonical support beyond tolerance, color-only cannot create it without opacity/background cheating; quantify support symmetric difference and minimum displacement.

### F. Iteration 1 bottom line

- Strengthened: `quantile_max`/monotone materialization is a concrete first spike. It preserved coverage in the proxy and improved the goose+nubzuki conflict tail.
- Weakened: `color-aware OT` is not proven as a universal upgrade. In goose+cake, this simple color-aware proxy slightly worsened conflict.
- Refined: 3-view exact feasibility needs row-graph isolation and density certificates.
- Refined: directional color needs pop/leakage regularizers before any shader recommendation.

---

## Iteration 2 — real top-candidate graph certificate + directional lobe regularizer

Scope guard:
- Branch checked earlier in this iteration: `algorithm-exploration-20260518`.
- Production files not modified. New/changed files are only under `artifacts/.hermes/` and `artifacts/algorithm-exploration/`.
- Read required prior outputs: `deep-algorithm-proposal-20260518.md`, `verification-plan-20260518.md`, `algorithm_exploration_probe_20260518.json`, and this iterative log.

Iteration-specific files:
- `artifacts/.hermes/iteration2_graph_and_lobe_probe_20260518.py`
- `artifacts/algorithm-exploration/iteration-2-graph-and-lobe-probe-20260518.json`
- `artifacts/algorithm-exploration/iteration-2-graph-lobe-deepening-20260518.md`

### A. Critique of previous conclusion

The previous conclusion is not wrong, but it was still shallow in the following ways:

1. The 3-view visual-hull theorem was too global. It said exact feasibility is `π(H)=A/B/C`, but did not separate the certificates that explain failure:

```text
isolatedFront(x,y) = [x∈X_y and no z∈Z_y with C(x,z)=1]
isolatedSide(z,y)  = [z∈Z_y and no x∈X_y with C(x,z)=1]
unsupportedTop(x,z)= [C(x,z)=1 and no y with x∈X_y and z∈Z_y]
```

2. The prior 3-view experiment was still synthetic. A synthetic diagonal/cutout top does not test whether actual `phoenix.png` or `kumdori.png` supports can be generated by the front/right same-row coactivity envelope.

3. The row OT recommendation risked overclaiming. Iteration 1 showed `quantile_max` helped `goose+nubzuki` but slightly worsened `goose+cake`; therefore full OT/Sinkhorn is not yet justified as the next production algorithm. The safer spike is current max+reuse baseline → quantile materialization → local color-aware only if repeatably beneficial.

4. Directional color still lacked a basis selection rule. Endpoint fit alone is insufficient. The missing conditions are:

```text
endpointLeak = wrong lobe weight at canonical views
pathError    = RMSE(weight_right(θ), desired_mid_angle_weight(θ))
pop          = max_θ |w(θ+Δ)-w(θ)|
accel        = max_θ |w(θ+Δ)-2w(θ)+w(θ-Δ)|
```

### B. New concrete progress: real-image top graph probe + lobe sweep

I added and ran a throwaway iteration-2 probe. It uses real reference images, still as a proxy extraction rather than the production renderer:

- front: `goose.png`
- side: `nubzuki.png`, `cake.png`
- top candidates: `phoenix.png`, `kumdori.png`
- graph resolution: `96×80×96`
- output: `artifacts/algorithm-exploration/iteration-2-graph-and-lobe-probe-20260518.json`

The same script sweeps directional lobe families:

- `normalized_cosine_power`
- `angular_gaussian`
- `softmax_cosine`

### C. Real top-candidate 3-view results

All tested real top candidates fail exact 3-view feasibility in this proxy.

```text
goose + nubzuki + phoenix:
  front_iou=0.537862, side_iou=0.494927, top_iou=0.327256
  missing_front=415, missing_side=896, missing_top=2952
  unsupported_top_ratio=0.672744
  exact_pass_098=false

goose + nubzuki + kumdori:
  front_iou=0.537862, side_iou=0.510710, top_iou=0.416485
  missing_front=415, missing_side=868, missing_top=2683
  unsupported_top_ratio=0.583515
  exact_pass_098=false

goose + cake + phoenix:
  front_iou=0.925390, side_iou=0.638850, top_iou=0.458523
  missing_front=67, missing_side=1294, missing_top=2376
  unsupported_top_ratio=0.541477
  exact_pass_098=false

goose + cake + kumdori:
  front_iou=0.925390, side_iou=0.662015, top_iou=0.537625
  missing_front=67, missing_side=1211, missing_top=2126
  unsupported_top_ratio=0.462375
  exact_pass_098=false
```

Interpretation:

- `phoenix/kumdori` should not be treated as arbitrary plug-in top views. Their top pixels are mostly not supportable by the front/right same-row coactivity envelope.
- `goose+cake` preserves front better than `goose+nubzuki`, because cake has broader row support, but side/top are still far below acceptance.
- High row edge density does not imply exact feasibility. Example: `goose+cake+kumdori` has `row_edge_density_mean=0.993705`, but top IoU is only `0.537625` because many top pixels have no compatible `y`.

This yields a stronger top-image design condition:

```text
S = ⋃_y X_y × Z_y
Top support feasibility requires C ⊆ S.
Front preservation requires ∀(x,y)∈A, C_x ∩ Z_y ≠ ∅.
Side preservation requires ∀(z,y)∈B, C^z ∩ X_y ≠ ∅.
```

So iteration 2 refines the recommendation from “run visual hull QA” to “constrain or generate the top candidate from `S` before visual hull QA.”

### D. Directional color lobe sweep results

Selected basis-weight results:

```text
normalized_cosine_power s=1:
  endpoint leakage=0
  linear_path_rmse=0.031562
  max_5deg_weight_jump=0.080450
  max_accel=0.011004

normalized_cosine_power s=8:
  endpoint leakage=0
  linear_path_rmse=0.216266
  max_5deg_weight_jump=0.302724
  max_accel=0.160076

normalized_cosine_power s=16:
  endpoint leakage=0
  linear_path_rmse=0.246995
  max_5deg_weight_jump=0.443043
  max_accel=0.389414

angular_gaussian sigma=0.50 rad:
  endpoint leakage=0.007141
  linear_path_rmse=0.121161
  max_5deg_weight_jump=0.133744
  max_accel=0.027305

angular_gaussian sigma=0.75 rad:
  endpoint leakage=0.100359
  linear_path_rmse=0.042712
  max_5deg_weight_jump=0.060624
  max_accel=0.005655

softmax_cosine temperature=0.35:
  endpoint leakage=0.054313
  linear_path_rmse=0.052711
  max_5deg_weight_jump=0.087142
  max_accel=0.012120
```

The previous toy result around sharp lobe `s=8` was misleading if interpreted as acceptable. It has perfect endpoint separation but a large mid-angle switch. First shader spike should therefore avoid sharp `s=8/s=16` as default.

Updated basis recommendation:

```text
Start with normalized_cosine_power s=1 or softmax_cosine τ≈0.35.
Use angular_gaussian σ≈0.50 only if stronger endpoint separation is required and pop metrics pass.
Reject sharp lobes unless max_5deg_weight_jump and acceleration are visually acceptable.
```

Regularized fitting objective for the spike:

```text
min_β  L_endpoint(0°,90°)
     + λ_path Σθ ||c(θ)-c_target(θ)||²
     + λ_jump maxθ ||c(θ+Δ)-c(θ)||²
     + λ_accel Σθ ||c(θ+Δ)-2c(θ)+c(θ-Δ)||²
     + λ_leak wrongLobeEndpoint
```

### E. Updated implementation spike order

1. Keep production unchanged.
2. Build a reusable throwaway harness that mirrors `src/main.ts` extraction more closely.
3. Row matching: current max+reuse baseline → `quantile_max` → local color-aware only if repeatably beneficial; defer full Sinkhorn.
4. Directional color: run basis sweep and real-color endpoint RMSE before shader integration; default to smooth bases, not sharp lobes.
5. 3-view: compute `S=⋃_y X_y×Z_y`; reject arbitrary top images if `|C\S|/|C|` is high; only then run `H=A∧B∧C`.
6. Never add production top/projection-only/fallback points during this exploration.

### F. Open questions for iteration 3

1. Mirror `src/main.ts` extraction exactly in the throwaway harness: canvas size, active-bound normalization, row count, stride, and deterministic shuffle.
2. Generate a top candidate constrained to `S` and measure recognizability vs exact feasibility. Arbitrary `phoenix/kumdori` are now shown weak.
3. If a compatible top is generated, solve sparse sampling of `H` while preserving all projections. This is a set-cover/hitting problem, not random downsampling.
4. Apply directional basis sweep to actual paired point colors and compare endpoint RMSE against current fixed blend.
5. Define visible-pop thresholds with contact sheets/rendered sequence, mapping weight jumps to perceptual ΔE/RMSE.
6. Add executable support-difference test for angular morph: if target support differs from canonical support beyond a small dilation tolerance, classify as geometry-needed.

### G. Iteration 2 bottom line

- Strengthened: 3-view exact feasibility now has a real-image graph/top-support certificate. Phoenix/kumdori fail as arbitrary top views in this proxy.
- Strengthened: top selection should be constrained by `S=⋃_y X_y×Z_y` before point generation.
- Strengthened: directional color now has a concrete basis/regularizer recommendation; sharp lobes are risky because of mid-angle pop.
- Weakened: the earlier “s=8 lobe fits endpoints” observation is not sufficient for implementation.
- Still uncertain: extraction remains proxy, not exact production renderer output. Iteration 3 should close that gap before any code-change recommendation.

---

# Iteration 3 — production-like extraction + feasible-top synthesis

Scope guard:
- Branch checked by tool: `algorithm-exploration-20260518`.
- Production files were read for extraction constants, but not modified.
- New/changed files are only under `artifacts/.hermes/` and `artifacts/algorithm-exploration/`.
- Required prior outputs were read: `deep-algorithm-proposal-20260518.md`, `verification-plan-20260518.md`, `algorithm_exploration_probe_20260518.json`, and `iterative-deepening-log-20260518.md`.

Iteration-specific files:
- `artifacts/.hermes/iteration3_production_like_and_top_synthesis_20260518.py`
- `artifacts/algorithm-exploration/iteration-3-production-like-and-top-synthesis-20260518.json`
- `artifacts/algorithm-exploration/iteration-3-production-like-and-top-synthesis-20260518.md`

## A. Critique of previous conclusions

Iteration 1 and 2 made real progress, but the prior outputs were still shallow in four places.

1. The real-image probes were not close enough to the production extraction path. Production uses:

```text
MASK_WIDTH=960, MASK_HEIGHT=280, ROW_COUNT=190, SAMPLE_STRIDE=1
margin=28 while drawing the reference image
active iff alpha >= 64
row = floor(((py-minActiveY)/(maxActiveY-minActiveY)) * (ROW_COUNT-1))
```

Iteration 1 used `192×96`; iteration 2 used `96×80×96`. Those were useful but could misstate row overlap, duplicate multiplicity, and color conflict. This iteration mirrors the production constants in a throwaway script.

2. Row OT/quantile was still discussed too abstractly. The real implementation does not just choose `(x,z)`; it also shuffles with a seeded RNG, then feeds paired colors into a non-linear signal-biased blend. Therefore the missing metric was endpoint color error after the production-like blend:

```text
E_fixed = 0.5 * mean_i( ||blend(cF_i,cS_i)-cF_i|| + ||blend(cF_i,cS_i)-cS_i|| )
```

3. Directional color had basis/pop metrics, but not actual paired-color endpoint error. Endpoint leakage translates to real error proportional to `||cF-cS||`; this iteration measures it on the actual paired samples.

4. The 3-view conclusion still had a gap between “arbitrary top fails” and “generate a compatible top”. A compatible top must be a subset of the coactivity envelope:

```text
S = union_y X_y × Z_y
C must satisfy C ⊆ S for all top pixels to be supportable.
```

But that is not enough for recognizability. This iteration synthesizes a sparse `C_gen` biased toward the real top image and measures `IoU(C_gen, C_target)`. This exposes the core trade-off: exact-feasible top supports become too sparse/low-recall to look like phoenix/kumdori.

## B. New concrete progress

I added and ran a new throwaway probe:

```text
python artifacts/.hermes/iteration3_production_like_and_top_synthesis_20260518.py
```

It writes:

```text
artifacts/algorithm-exploration/iteration-3-production-like-and-top-synthesis-20260518.json
```

The script does four things:

1. Mirrors production image drawing/extraction constants from `src/main.ts`.
2. Compares:
   - `current_shuffled_max_reuse`
   - `quantile_max`
   - `local_color_quantile`
3. Computes actual paired-color endpoint error for fixed blend vs directional bases:
   - `cosine_s1`
   - `cosine_s2`
   - `softmax_tau035`
   - `gaussian_sigma05`
4. Generates an exact-top-support candidate `C_gen` from front/side coactivity, biased toward `phoenix`/`kumdori`, and reports recognizability against the real top target.

Important limitation: this is still a Python proxy for browser canvas/PIL resampling, not a browser render capture. It is much closer to production constants than prior probes, but not bit-identical to JS canvas interpolation or the JS LCG shuffle.

## C. Production-like row materialization results

### goose + nubzuki

```text
current_shuffled_max_reuse:
  points=11305, front_iou=0.837755, side_iou=0.799430
  conflict_mean=0.423812, conflict_p95=0.822530
  fixed_blend_endpoint_rmse=0.214371
  z_jump_mean=34.464, z_jump_p95=90

quantile_max:
  same point count and IoU
  conflict_mean=0.391630  (7.59% lower)
  conflict_p95=0.681958  (17.09% lower)
  fixed_blend_endpoint_rmse=0.198474  (7.42% lower)
  z_jump_mean=0.946  (97.26% lower)

local_color_quantile:
  front_iou=0.837755, side_iou=0.797632  (-0.001798 absolute side IoU)
  conflict_mean=0.390047  (7.97% lower)
  conflict_p95=0.674985  (17.94% lower)
  fixed_blend_endpoint_rmse=0.197699  (7.78% lower)
```

Interpretation: for goose+nubzuki, monotone/quantile pairing is no longer just a nice mathematical replacement. Under production-like extraction it materially reduces row-wise z discontinuity and color conflict tail without changing point budget or projection coverage. Local color search gives a small additional color benefit but slightly harms side coverage and duplicate balance.

### goose + cake

```text
current_shuffled_max_reuse:
  points=20745, front_iou=1.000000, side_iou=0.755999
  conflict_mean=0.480347, conflict_p95=0.807354
  fixed_blend_endpoint_rmse=0.242625
  z_jump_mean=48.692, z_jump_p95=116

quantile_max:
  same point count and IoU
  conflict_mean=0.480426  (0.016% worse)
  conflict_p95=0.810899  (0.439% worse)
  fixed_blend_endpoint_rmse=0.242689  (0.026% worse)
  z_jump_mean=0.966  (98.02% lower)

local_color_quantile:
  side_iou=0.755923  (-0.000076 absolute side IoU)
  conflict_mean=0.479646  (0.146% lower)
  conflict_p95=0.810668  (0.410% worse)
  fixed_blend_endpoint_rmse=0.242309  (0.130% lower)
```

Interpretation: for goose+cake, quantile materialization is not a color win, but it is a major spatial-continuity win. The implementation spike should therefore sell `quantile_max` as a row continuity / reveal-stability improvement, not as a guaranteed color improvement. Color-aware local search is still not proven worth production complexity.

## D. Directional color endpoint result on real paired colors

Fixed blend endpoint error is substantial:

```text
goose+nubzuki fixed_blend_endpoint_rmse ≈ 0.198–0.214 depending pairing
goose+cake    fixed_blend_endpoint_rmse ≈ 0.242
```

Directional endpoint errors:

```text
cosine_s1 / cosine_s2: endpoint_rmse=0.0 in this idealized endpoint model
softmax_tau035: endpoint_rmse≈0.021–0.026, about 89% better than fixed blend
gaussian_sigma05: endpoint_rmse≈0.0028–0.0034, about 98.6% better than fixed blend
```

This strengthens the recommendation for directional material, but with a caveat:

- Endpoint fit is now clearly better than fixed blend.
- The basis choice must still be governed by iteration-2 pop metrics.
- `cosine_s1` has perfect endpoint separation and good path smoothness in the basis-only metric, so it is the safest first shader candidate if the desired intermediate transition is a smooth physical morph.
- `gaussian_sigma05` has excellent endpoint error but higher path error/jump than `cosine_s1`; use only if endpoint color separation is more important than mid-angle smoothness.
- No opacity gate is needed for these endpoint improvements.

## E. Top synthesis / 3-view feasibility result

The generated top experiment makes a blunt point: exact-feasible top supports exist, but they are not recognizable as arbitrary real top images.

### Coactivity envelope limits

```text
goose+nubzuki+phoenix: target_inside_S_ratio=0.128686
goose+nubzuki+kumdori: target_inside_S_ratio=0.151123
goose+cake+phoenix:    target_inside_S_ratio=0.168901
goose+cake+kumdori:    target_inside_S_ratio=0.196891
```

Only about 13–20% of real top pixels lie inside the front/side coactivity envelope under production-like extraction. This is stronger evidence than iteration 2: arbitrary `phoenix/kumdori` cannot be treated as real top views for this front/side pair.

### Greedy exact-support top, biased toward target

```text
goose+nubzuki+phoenix: generated_vs_target_iou=0.083929, precision=0.989474, recall=0.084004
goose+nubzuki+kumdori: generated_vs_target_iou=0.107945, precision=1.000000, recall=0.107945
goose+cake+phoenix:    generated_vs_target_iou=0.120643, precision=1.000000, recall=0.120643
goose+cake+kumdori:    generated_vs_target_iou=0.150259, precision=1.000000, recall=0.150259
```

High precision but very low recall means the generated top mostly chooses target-compatible pixels, but far too few of them to recreate the real top silhouette. In visual terms: a top view constrained to be valid would look like a sparse skeleton/stencil, not phoenix/kumdori.

The self-projection top IoU is 1.0 by construction, but front/side exact pass is capped by the already-existing row-overlap limit:

```text
goose+nubzuki generated top: front_iou≈0.840105, side_iou≈0.798917
goose+cake generated top:    front_iou=1.000000, side_iou≈0.755777
```

This is not a top-synthesis bug; it reveals a deeper condition missing from earlier feasibility statements:

```text
2-view row-overlap upper bound:
A can only be covered on rows y where Z_y is non-empty.
B can only be covered on rows y where X_y is non-empty.
```

So before 3-view feasibility, we need a 2-view row-support certificate:

```json
{
  "frontPixelsInMatchedRowsRatio": "upper bound on front projection coverage",
  "sidePixelsInMatchedRowsRatio": "upper bound on side projection coverage",
  "frontOnlyRows": "rows with A but no B",
  "sideOnlyRows": "rows with B but no A"
}
```

## F. Updated mathematical conditions

The exact 3-view theorem remains:

```text
H = {(x,y,z): A(x,y)=1 and B(z,y)=1 and C(x,z)=1}
exact iff pi_xy(H)=A, pi_zy(H)=B, pi_xz(H)=C
```

Iteration 3 adds a more operational feasibility ladder:

```text
Step 0: 2-view y-support upper bound
  For all (x,y) in A, need Z_y != empty.
  For all (z,y) in B, need X_y != empty.

Step 1: top coactivity envelope
  S = union_y X_y × Z_y.
  Necessary for top exactness: C ⊆ S.

Step 2: row graph coverage
  For every (x,y) in A, exists z in Z_y with (x,z) in C.
  For every (z,y) in B, exists x in X_y with (x,z) in C.

Step 3: density/reveal budget
  |H|, row edge count p95/max, duplicate/multiplicity histograms.

Step 4: recognizability of generated/filtered top
  IoU(C_generated, C_target), precision, recall, connected components / skeletonization score.
```

This changes the top recommendation: do not merely “generate a compatible top”. A compatible top must also pass recognizability metrics. Current phoenix/kumdori candidates fail that recognizability threshold badly.

## G. Updated implementation spike order

1. Keep production unchanged until a browser-equivalent harness confirms these numbers.
2. First production candidate: `quantile_max` row materialization, not full OT/Sinkhorn.
   - Reason: enormous continuity improvement, same point count, same coverage; color benefits are pair-dependent.
3. Do not add local color-aware matching yet.
   - It gives only marginal color gains and sometimes worsens p95/coverage.
4. First shader candidate: directional color basis with smooth basis/pop QA.
   - Start with `cosine_s1` or another smooth low-pop basis.
   - Measure endpoint RMSE, mid-angle max jump, acceleration, and rendered contact sheets.
5. 3-view remains research-only.
   - Add a 2-view row-support certificate and top coactivity envelope check before any visual-hull solver.
   - Reject arbitrary top images when `target_inside_S_ratio` is low.
   - Generated compatible top must be evaluated for recognizability, not only exactness.

## H. Open questions for iteration 4

1. Run the same extraction in a browser/Node canvas harness to remove PIL-vs-canvas resampling uncertainty.
2. Add visual contact sheets for current shuffle vs quantile rows; the z-jump metric predicts less barcode/reveal chaos, but visual proof is still needed.
3. Add matched-row upper-bound metrics directly to the JSON: front/side pixels in rows where the other view is non-empty.
4. Improve top synthesis from greedy row cover to an explicit optimization:

```text
min_C  λ_target * d(C, C_target)
     + λ_coverA * uncovered_A(C)
     + λ_coverB * uncovered_B(C)
     + λ_sparse * |C|
     + λ_shape * components/skeleton penalty
subject to C ⊆ S
```

5. Evaluate whether a third view should be designed from the start together with front/right, rather than adapted from independent phoenix/kumdori assets.
6. Directional color needs rendered mid-angle evidence, not just endpoint metrics.

## I. Iteration 3 bottom line

- Strengthened: `quantile_max` is the safest row-materialization spike. It preserves coverage and drastically reduces row discontinuity; color gains are real for goose+nubzuki but not universal.
- Strengthened: directional color basis has a very large endpoint-error advantage over fixed blend on actual paired colors, but pop metrics still decide the basis.
- Strengthened: arbitrary real top images are not just infeasible; even target-biased exact-compatible generated tops have only about 8–15% IoU/recall against phoenix/kumdori. That is not production-worthy.
- Refined: 3-view feasibility must start with a 2-view y-support upper bound and a top coactivity-envelope/recognizability certificate before visual hull generation.

---

# Iteration 4 — feasibility ladder + angular morph support test

Scope guard:
- Branch checked by tool: `algorithm-exploration-20260518`.
- Production files were not modified.
- New throwaway script: `artifacts/.hermes/iteration4_feasibility_ladder_and_morph_probe_20260518.py`.
- New result JSON: `artifacts/algorithm-exploration/iteration-4-feasibility-ladder-and-morph-probe-20260518.json`.
- Iteration-specific report: `artifacts/algorithm-exploration/iteration-4-feasibility-ladder-and-morph-deepening-20260518.md`.
- Required prior outputs were read again: base proposal, verification plan, original probe JSON, and this iterative log through iteration 3.

## A. Critique of previous conclusions

Iteration 3 made the strongest progress so far, but it was still shallow in five places.

1. The 2-view row-overlap cap was only inferred from final IoU. The missing formal gate is:

```text
U_A = {(x,y) in A : Z_y is non-empty}
U_B = {(z,y) in B : X_y is non-empty}
max possible front coverage <= |U_A|/|A|
max possible side  coverage <= |U_B|/|B|
```

If a row exists in only one image, no exact shared 3D point can represent it without projection-only/fallback points. This must be checked before top/3-view exploration.

2. Top synthesis was still a single greedy construction. It did not separate `C=target∩S` (best exact-support target recall/precision) from row-covering `C` (best front/side preservation under a target bias). Those choices answer different questions.

3. Top slack/dilation was not operational. Dilation only helps if new useful pixels enter the coactivity envelope `S`; otherwise it merely adds supportable off-target pixels and lowers precision.

4. Angular morph had no hard decision rule. The missing necessary condition for color-only is:

```text
B_target subset dilate(B_canonical, eps)
and
B_canonical subset dilate(B_target, eps)
```

If this fails at the accepted physical tolerance, color-only cannot create/delete silhouette support without opacity/background cheating.

5. All current real-image experiments remain PIL/canvas proxies. Browser render parity and visual contact sheets are still unverified.

## B. New concrete progress

I added and ran an iteration-4 throwaway probe:

```text
python artifacts/.hermes/iteration4_feasibility_ladder_and_morph_probe_20260518.py
```

It adds:

1. 2-view row-support upper-bound certificate.
2. Top-support trade-off sweep:
   - `target_dilation_intersection`: `C = dilate(C_target,r) ∩ S`
   - `cover_greedy_biased_to_dilated_target`: row-covering top support biased toward target/dilated target
3. Angular morph support-difference test on `goose`, using synthetic support shifts by 2/4/8/16 px.

## C. 2-view row-support upper-bound results

### goose + nubzuki

```text
front_pixels_in_matched_rows_ratio = 0.840105
side_pixels_in_matched_rows_ratio  = 0.798917
front_only_row_count = 24
side_only_row_count  = 29
matched_row_count    = 120
```

This explains why generated/self-exact top attempts for goose+nubzuki cap out near front IoU 0.840 and side IoU 0.799. The cap exists before top is considered.

### goose + cake

```text
front_pixels_in_matched_rows_ratio = 1.000000
side_pixels_in_matched_rows_ratio  = 0.755777
front_only_row_count = 0
side_only_row_count  = 46
matched_row_count    = 144
```

This explains why goose+cake can preserve the front but cannot preserve all side rows. Cake has many rows where goose has no corresponding row support.

Updated rule: fail fast or warn before 3-view if these upper bounds are below the desired canonical IoU threshold.

## D. Top trade-off sweep result

The sweep did not rescue arbitrary phoenix/kumdori top views.

```text
goose+nubzuki+phoenix: target_inside_S_ratio = 0.128686
goose+nubzuki+kumdori: target_inside_S_ratio = 0.151123
goose+cake+phoenix:    target_inside_S_ratio = 0.168901
goose+cake+kumdori:    target_inside_S_ratio = 0.196891
```

Using `C=target∩S` gives precision 1.0 and recall equal to those ratios, but cannot exceed them. Best case, `goose+cake+kumdori`, is still weak:

```text
C=target∩S:
  top_vs_original_target_iou = 0.196891
  top_precision = 1.000000
  top_recall    = 0.196891
  front_iou     = 1.000000
  side_iou      = 0.755777
  row_edge_count_p95 = 160

greedy row-cover biased to target:
  top_vs_original_target_iou = 0.150259
  top_precision = 1.000000
  top_recall    = 0.150259
  front_iou     = 1.000000
  side_iou      = 0.755777
```

Target dilation did not improve original-target recall; for phoenix it mainly lowered precision by adding off-target supportable pixels. The limitation is not a small alignment radius. The coactivity envelope `S` is too small/misaligned relative to independent phoenix/kumdori assets.

Updated feasibility ladder:

```text
0. 2-view row-support upper bound: |U_A|/|A|, |U_B|/|B|
1. Coactivity envelope: S = union_y X_y × Z_y
2. Top support choice: C_target∩S vs row-cover C
3. Visual hull certificate: H = A ∧ B ∧ C
4. Density/reveal certificate: |H|, row_edge_count p50/p95/max
5. Recognizability: IoU/precision/recall/components against intended top
```

## E. Angular morph decision test

Synthetic goose support shifts:

```text
same support color-only: pass at eps=0
2px shift:  raw_iou=0.913158, first tolerance covering both supports = 2px
4px shift:  raw_iou=0.834060, first tolerance covering both supports = 4px
8px shift:  raw_iou=0.694206, first tolerance covering both supports = 8px
16px shift: raw_iou=0.475172, no pass up to eps=8px
```

Decision gate:

```text
supportShiftEps = smallest eps such that
  target_support subset dilate(canonical_support, eps)
  and canonical_support subset dilate(target_support, eps)

if supportShiftEps == 0: color-only feasible
elif supportShiftEps <= 2: micro-displacement candidate
elif supportShiftEps <= 4: borderline research-only
else: geometry-needed / defer
```

This makes the earlier “팔 움직임이면 geometry-needed일 수 있다” claim testable.

## F. Updated implementation spike order

1. Add browser-equivalent extraction/render harness before production code changes.
2. Row materialization spike remains `quantile_max` first.
3. Directional color spike remains valid, but must include rendered mid-angle contact sheet and pop metrics.
4. Add 2-view row-support upper-bound QA before any 3-view/top attempt.
5. Keep arbitrary phoenix/kumdori top out of production. Current numbers are far below recognizability and exact side/front thresholds.
6. For angular morph, implement the support-difference classifier first; only then consider micro-displacement experiments.

## G. Open questions for next iteration

1. Browser/Node canvas parity: reproduce iteration-3/4 extraction with JS canvas, not PIL.
2. Visual evidence: contact sheets for current shuffle vs quantile rows and directional color mid-angles.
3. Top recognizability metric needs connected-component/skeleton metrics, not only IoU/recall.
4. Investigate co-designed 3-view assets: if front/right/top are designed jointly, can `target_inside_S_ratio` exceed 0.8 while staying recognizable?
5. If row support mismatch is caused by active-bound normalization, test whether controlled vertical alignment/cropping improves the 2-view upper bound without cheating.
6. For morph, test localized limb shifts instead of whole-object shifts; whole-object shift is a strict synthetic bound, not a real animation case.

## H. Iteration 4 bottom line

- Strengthened: before any 3-view solver, the pipeline needs a 2-view row-support upper-bound certificate. It explains the observed IoU ceilings.
- Strengthened: arbitrary phoenix/kumdori top views remain infeasible/low-recognition even with target dilation and greedy support trade-offs.
- Strengthened: angular morph now has a concrete support-difference gate separating color-only, micro-displacement candidate, borderline research, and geometry-needed cases.
- Still uncertain: browser render parity and visual contact sheets are not yet done.

---

# Iteration 5 — top recognizability metrics + row-alignment falsification

Scope guard:
- Branch checked by tool: `algorithm-exploration-20260518`.
- Production files were not modified.
- New throwaway script: `artifacts/.hermes/iteration5_shape_alignment_probe_20260518.py`.
- New result JSON: `artifacts/algorithm-exploration/iteration-5-shape-alignment-probe-20260518.json`.
- Iteration-specific report: `artifacts/algorithm-exploration/iteration-5-shape-alignment-deepening-20260518.md`.
- Required prior outputs were read again: base proposal, verification plan, original probe JSON, and this iterative log through iteration 4.

## A. Critique of previous conclusions

Iteration 4 was useful but still shallow in three places.

1. Top recognizability was judged mostly by IoU/precision/recall. That is not enough. A candidate can be one connected component with high precision and still be a tiny dense patch rather than a recognizable phoenix/kumdori. Missing recognizability metrics were:

```text
component_count(C)
largest_component_ratio(C)
isolated_pixel_ratio(C)
mean_8neighbor_count(C)
bbox_fill_ratio(C)
shape_delta(C, C_target)
```

2. The “active-bound normalization may cause row mismatch” uncertainty had not been falsified. If a simple integer row shift improved `front_pixels_in_matched_rows_ratio` or `side_pixels_in_matched_rows_ratio`, then the 2-view cap would be partly an alignment artifact.

3. The top-synthesis recommendation still did not state a necessary recognizability lower bound. Exact supportability is too weak. A production top candidate must satisfy both:

```text
C ⊆ S = union_y X_y × Z_y          # physical supportability
recall(C, C_target) high enough     # intended top remains legible
shape(C) close to shape(C_target)   # not a clipped dense blob
```

## B. New concrete progress

I added and ran:

```text
python artifacts/.hermes/iteration5_shape_alignment_probe_20260518.py
```

It writes:

```text
artifacts/algorithm-exploration/iteration-5-shape-alignment-probe-20260518.json
```

The probe adds:

1. Row-alignment sweep for side rows over `[-30, +30]` rows.
2. Shape/recognizability metrics for:
   - `C = C_target ∩ S`
   - `C = greedy row-cover biased to C_target ∩ S`

It remains a PIL proxy with production-like constants; browser parity is still unresolved.

## C. Row-alignment sweep result

### goose + nubzuki

```text
baseline shift 0:
  front_upper=0.840105
  side_upper=0.798917
  harmonic_upper=0.818993

best harmonic shift:
  side_row_shift=0
  front_upper=0.840105
  side_upper=0.798917
  harmonic_upper=0.818993

best minimum shift:
  side_row_shift=0
  front_upper=0.840105
  side_upper=0.798917
```

A simple row shift does not improve goose+nubzuki. The row-support cap is not explained by a constant vertical offset.

### goose + cake

```text
baseline shift 0:
  front_upper=1.000000
  side_upper=0.755777
  harmonic_upper=0.860903

best harmonic shift:
  side_row_shift=0
  front_upper=1.000000
  side_upper=0.755777
  harmonic_upper=0.860903

best minimum shift:
  side_row_shift=-30
  front_upper=0.901704
  side_upper=0.760597
```

For goose+cake, shifting can raise side upper bound only from `0.755777` to `0.760597`, while damaging front from `1.0` to `0.901704`. Therefore alignment/cropping cannot rescue the side mismatch in a useful way.

Updated conclusion: the 2-view y-support cap is structural for these assets under the current active-bound normalization. A row-shift/crop tweak is not a promising next spike.

## D. Top recognizability shape metrics

The target top masks are single connected dense shapes:

```text
phoenix target:
  pixels=1119, component_count=1, largest_component_ratio=1.0
  mean_8neighbor_count=7.352994, bbox_fill_ratio=0.647569

kumdori target:
  pixels=1158, component_count=1, largest_component_ratio=1.0
  mean_8neighbor_count=7.322971, bbox_fill_ratio=0.603125
```

The exact-support candidates are also often connected, so component count alone is not sufficient. The failure is recall/scale and shape-fill distortion.

Best available case, `goose + cake + kumdori`, with `C=target∩S`:

```text
IoU/recall vs target = 0.196891
precision = 1.000000
candidate pixels = 228 vs target 1158
component_count = 1
mean_8neighbor_count = 7.228070 vs target 7.322971
bbox_fill_ratio = 0.957983 vs target 0.603125
bbox_fill_ratio_delta = +0.354858
```

Interpretation: it is not random disconnected noise; it is one connected dense support patch. But it is only about 20% of the intended shape and has an overly filled bounding box. It will read as a clipped blob/stencil, not as kumdori.

Greedy row-cover candidate for the same case:

```text
IoU/recall vs target = 0.150259
precision = 1.000000
candidate pixels = 174 vs target 1158
mean_8neighbor_count = 7.034483
bbox_fill_ratio_delta = +0.127967
```

This preserves row-covering constraints but is even less recognizable.

Other cases remain far below any plausible recognizability threshold:

```text
goose+nubzuki+phoenix: target_inside_S=0.128686, greedy recall=0.084004
goose+nubzuki+kumdori: target_inside_S=0.151123, greedy recall=0.107945
goose+cake+phoenix:    target_inside_S=0.168901, greedy recall=0.120643
```

## E. Refined mathematical recommendation

The 3-view feasibility ladder now needs a recognizability gate after exact supportability:

```text
0. 2-view row support cap:
   U_A = {(x,y) in A : Z_y != empty}
   U_B = {(z,y) in B : X_y != empty}

1. Coactivity envelope:
   S = union_y X_y × Z_y
   top exactness requires C_target mostly inside S.

2. Exact top candidate:
   C_exact = C_target ∩ S, or optimized C ⊆ S.

3. Visual hull certificate:
   H = {(x,y,z): A(x,y) and B(z,y) and C(x,z)}
   require pi(H) close to A/B/C.

4. Recognizability certificate:
   recall(C, C_target) >= threshold
   abs(bbox_fill_ratio(C)-bbox_fill_ratio(C_target)) <= threshold
   mean_neighbor_delta within threshold
   component/largest-component not degenerate

5. Density/reveal certificate:
   |H|, row_edge_count p95/max, sampled density histogram.
```

Provisional recognizability thresholds for future experiments:

```text
recall(C, C_target) >= 0.70
IoU(C, C_target) >= 0.50
abs(bbox_fill_ratio_delta) <= 0.15
mean_8neighbor_count_delta >= -1.0
largest_component_ratio >= 0.80
```

Current phoenix/kumdori candidates fail primarily on recall/IoU, even when connectivity is not terrible.

## F. Updated implementation spike order

1. Keep production unchanged.
2. Browser-equivalent extraction/render harness remains the next verification blocker.
3. Row materialization candidate remains `quantile_max`; row-shift/cropping is not a useful rescue path for these assets.
4. Directional color remains the strongest near-term feature because fixed blend endpoint error is already shown large and no opacity/projection-only points are needed.
5. 3-view must stay research-only unless assets are co-designed so that `C_target ∩ S` recall is high. Arbitrary phoenix/kumdori top views remain rejected.
6. Future top generation should optimize under `C ⊆ S`, but target recognizability must be measured by recall + shape metrics, not exactness alone.

## G. Open questions for next iteration

1. Build a browser/Node canvas parity harness and compare PIL proxy metrics against actual JS/canvas extraction.
2. Generate visual contact sheets for `current_shuffled_max_reuse` vs `quantile_max` to confirm the z-jump improvement is visible.
3. Render directional color basis at mid-angles and compute visible pop/ΔE on actual paired colors.
4. Try co-designed top supports by constructing `C_target` from `S` first, then assessing whether humans can recognize it as a deliberate image.
5. Replace the simple shape metrics with skeleton/contour metrics if a library is allowed, because current `branchpoint_count` on filled shapes is only a rough density proxy.
6. Test localized limb morph support changes, not only whole-object shifts.

## H. Iteration 5 bottom line

- Strengthened: the row-support cap is not fixed by simple vertical alignment; shift 0 is already best for harmonic upper bound on both tested pairs.
- Strengthened: exact-supported top candidates fail recognizability mainly because recall is only about 8–20%, not because they are random disconnected noise.
- Refined: 3-view QA must include recognizability shape metrics after `C ⊆ S`; exact feasibility alone can produce a small connected but semantically useless blob.
- Still uncertain: browser parity and rendered visual evidence remain the two main verification gaps.

---

# Iteration 6 — visual contact sheets + actual paired-color pop metrics

Scope guard:
- Branch checked by tool at the start of this run: `algorithm-exploration-20260518`.
- Production files were not modified.
- New throwaway script: `artifacts/.hermes/iteration6_visual_and_directional_probe_20260518.py`.
- New result JSON: `artifacts/algorithm-exploration/iteration-6-visual-directional-probe-20260518.json`.
- New visual evidence:
  - `artifacts/algorithm-exploration/iteration-6-row-pairing-contact-sheet-20260518.png`
  - `artifacts/algorithm-exploration/iteration-6-directional-color-contact-sheet-20260518.png`
- Iteration-specific report: `artifacts/algorithm-exploration/iteration-6-visual-directional-deepening-20260518.md`.
- Required prior outputs were read again: base proposal, verification plan, original probe JSON, and this iterative log through iteration 5.

## A. Critique of previous conclusions

Iteration 5 strengthened the mathematical rejection of arbitrary top views, but two major weak spots remained.

1. The row-materialization recommendation still leaned heavily on scalar metrics. `z_jump_mean` and `z_jump_p95` predict reveal instability, but there was no visual artifact that a human could inspect. The missing evidence was a contact sheet showing whether current shuffle produces row-order chaos and whether `quantile_max` is actually monotone in representative dense rows.

2. Directional color had endpoint and basis-only pop metrics, but the most important pop risk is proportional to the actual paired color difference `||c_front-c_side||`. A sharp lobe can look okay in abstract weight space for low-conflict pairs but visibly pop on high-conflict pairs. The missing metric was:

```text
For each point pair i and angle theta:
  c_i(theta) = w_F(theta)c_F_i + w_R(theta)c_R_i

pop_step = max_theta mean_i ||c_i(theta+5deg)-c_i(theta)||
pop_tail = max_theta P99_i ||c_i(theta+5deg)-c_i(theta)||
accel    = max_theta mean_i ||c_i(theta+5)-2c_i(theta)+c_i(theta-5)||
```

3. The earlier “directional color endpoint is much better than fixed blend” conclusion was true but incomplete. It did not distinguish smooth endpoint-exact bases (`cosine_s1`) from endpoint-exact but pop-prone bases (`cosine_s8`). The implementation recommendation needed a sharper default/reject rule.

4. Browser parity is still not solved. This iteration remains a production-like PIL extraction/contact-sheet probe, not an actual browser capture. Therefore it improves evidence, but it is not yet final production verification.

## B. New concrete progress

I added and ran:

```text
python artifacts/.hermes/iteration6_visual_and_directional_probe_20260518.py
```

It writes:

```text
artifacts/algorithm-exploration/iteration-6-visual-directional-probe-20260518.json
artifacts/algorithm-exploration/iteration-6-row-pairing-contact-sheet-20260518.png
artifacts/algorithm-exploration/iteration-6-directional-color-contact-sheet-20260518.png
```

The script adds:

1. A row-pairing contact sheet comparing `current_shuffled_max_reuse` vs `quantile_max` for `goose+nubzuki` and `goose+cake`.
2. Row-order chaos metrics:
   - `z_jump_gt25_ratio`
   - `z_jump_gt50_ratio`
   - `normalized_total_variation_mean`
   - `direction_flip_ratio_mean`
3. Actual paired-color directional pop metrics over `goose+nubzuki` quantile pairs.
4. A directional-color contact sheet built from the high-conflict pair tail, so pop-prone transitions are easier to inspect.

## C. Row materialization: visual/sequence evidence

### goose + nubzuki

```text
current_shuffled_max_reuse:
  points=11305, front_iou=0.837755, side_iou=0.799430
  z_jump_mean=33.935807, z_jump_p95=89
  z_jump_gt25_ratio=0.518373, z_jump_gt50_ratio=0.243898
  normalized_total_variation_mean=0.341521
  direction_flip_ratio_mean=0.657731
  color_conflict_mean=0.422893, p95=0.817980

quantile_max:
  same points and same IoU
  z_jump_mean=0.945820, z_jump_p95=1
  z_jump_gt25_ratio=0.000000, z_jump_gt50_ratio=0.000000
  normalized_total_variation_mean=0.012906
  direction_flip_ratio_mean=0.000000
  color_conflict_mean=0.391630, p95=0.681958
```

This is now stronger than iteration 3: not only average jump but also large-jump ratio and direction-flip ratio collapse to zero under `quantile_max`. This supports the claim that quantile materialization is a reveal-stability improvement, not only a color heuristic.

### goose + cake

```text
current_shuffled_max_reuse:
  points=20745, front_iou=1.000000, side_iou=0.755999
  z_jump_mean=49.162516, z_jump_p95=117
  z_jump_gt25_ratio=0.679287, z_jump_gt50_ratio=0.427358
  normalized_total_variation_mean=0.338576
  direction_flip_ratio_mean=0.667049
  color_conflict_mean=0.480180, p95=0.806436

quantile_max:
  same points and same IoU
  z_jump_mean=0.965681, z_jump_p95=1
  z_jump_gt25_ratio=0.000000, z_jump_gt50_ratio=0.000000
  normalized_total_variation_mean=0.008610
  direction_flip_ratio_mean=0.000000
  color_conflict_mean=0.480426, p95=0.810899
```

This refines the recommendation:

- `quantile_max` is not guaranteed to reduce color conflict (`goose+cake` color conflict is slightly worse).
- But it is consistently better on row-order continuity and does not hurt point count or projection IoU in these probes.
- Therefore the correct production spike claim is: “quantile materialization reduces row/reveal chaos with no projection cost,” not “quantile always improves color.”

## D. Directional color actual pair pop metrics

Measured on `goose+nubzuki` using `quantile_max` pair colors.

```text
cosine_s1:
  endpoint_rmse=0.000000
  linear_path_rmse=0.010745
  max_5deg_step_mean=0.031507
  max_5deg_step_pair_p99=0.071634
  max_accel=0.004310
  endpoint wrong-lobe weights=0

cosine_s2:
  endpoint_rmse=0.000000
  linear_path_rmse=0.025044
  max_5deg_step_mean=0.034003
  max_5deg_step_pair_p99=0.077309
  max_accel=0.005859

cosine_s8:
  endpoint_rmse=0.000000
  linear_path_rmse=0.071455
  max_5deg_step_mean=0.118556
  max_5deg_step_pair_p99=0.269548
  max_accel=0.062691

softmax_tau035:
  endpoint_rmse=0.021271
  linear_path_rmse=0.018438
  max_5deg_step_mean=0.034127
  max_5deg_step_pair_p99=0.077592
  max_accel=0.004747
  endpoint wrong-lobe weight=0.054313

gaussian_sigma05:
  endpoint_rmse=0.002796
  linear_path_rmse=0.041162
  max_5deg_step_mean=0.052378
  max_5deg_step_pair_p99=0.119087
  max_accel=0.010693
  endpoint wrong-lobe weight=0.007141
```

Updated basis decision:

```text
Default first shader candidate: cosine_s1
Reason: endpoint-exact, lowest actual-pair path error, low step, low acceleration, no leakage.

Acceptable alternative: softmax_tau035
Reason: smooth and low acceleration, but endpoint leakage causes nonzero endpoint RMSE.

Use with caution: gaussian_sigma05
Reason: excellent endpoint error but more mid-angle path error and higher tail step than cosine_s1.

Reject as default: cosine_s8/sharp lobes
Reason: endpoint-exact but max_5deg_step_mean is ~3.76x cosine_s1 and p99 step is ~3.76x cosine_s1. This is a concrete pop risk on actual high-conflict pairs.
```

## E. Updated mathematical/metric recommendation

### Row materialization gate

Add these to the row-matching experiment before production promotion:

```json
{
  "projectionOnlyPointCount": 0,
  "front_iou_delta_vs_current": ">= -0.005",
  "side_iou_delta_vs_current": ">= -0.005",
  "z_jump_gt25_ratio_delta": "large negative preferred",
  "z_jump_gt50_ratio_delta": "large negative preferred",
  "direction_flip_ratio_mean": "near 0 for quantile/monotone policies",
  "color_conflict_mean_delta": "report, but do not require universal improvement"
}
```

### Directional color gate

Use actual paired colors, not only basis weights:

```text
endpoint_rmse_mean <= fixed_blend_endpoint_rmse * 0.25
max_5deg_step_mean <= 0.04 initially
max_5deg_step_pair_p99 <= 0.10 initially
max_accel_rmse_mean <= 0.01 initially
wrong_lobe_endpoint <= 0.06 if endpoint leakage is accepted
```

These thresholds are provisional. They need browser rendered contact sheets before becoming hard production thresholds.

## F. Updated implementation spike order

1. Keep production unchanged.
2. Browser/Node canvas parity remains the verification blocker, but the spike target is now more concrete:
   - replicate this iteration’s row contact sheet in JS/canvas or browser capture.
3. Implement candidate row materialization in a throwaway JS harness first:
   - `current_shuffled_max_reuse` baseline
   - `quantile_max`
   - same metrics as iteration 6
4. Directional color shader spike should start with `cosine_s1` and include actual-pair pop metrics plus rendered mid-angle contact sheet.
5. Do not spend next spike on full Sinkhorn or arbitrary 3-view. The strongest near-term improvement is row continuity + directional color.
6. Keep 3-view research-only unless co-designed assets pass row-support, `C⊆S`, recognizability, visual-hull, and density gates.

## G. Open questions for next iteration

1. Browser parity: run the same extraction/materialization metrics in JS/canvas or actual browser render capture.
2. Compare the saved row contact sheet against real reveal-frame artifacts; a monotone z-sequence should reduce barcode/reveal chaos, but this still needs rendered evidence.
3. Directional color contact sheet should be rendered through the actual point shader/splat size, not just RGB swatches.
4. Test `cosine_s1` on `goose+cake`, not only `goose+nubzuki`, especially because `goose+cake` has higher conflict and worse row-support mismatch.
5. Define perceptual thresholds from real screenshots: whether p99 5-degree color step of 0.07 is visually acceptable depends on splat size/glow/background.
6. If iteration 7 is the final iteration, write the final one-hour recommendation with: iteration count, mathematical feasibility ladder, verification metrics, and implementation spike order.

## H. Iteration 6 bottom line

- Strengthened: `quantile_max` has direct visual/sequence evidence now. It preserves projection IoU and point count while eliminating large row jumps and direction flips in the tested probes.
- Refined: color conflict improvement is pair-dependent; do not justify `quantile_max` primarily as a color optimizer.
- Strengthened: directional color should default to smooth `cosine_s1`; sharp lobes are now rejected by actual paired-color pop metrics, not just abstract intuition.
- Still uncertain: browser parity and actual shader-rendered contact sheets remain unresolved.

---

# Iteration 7 — decision gates for row materialization and directional color

Scope guard:
- Branch checked by tool: `algorithm-exploration-20260518`.
- Production files were not modified.
- New throwaway script: `artifacts/.hermes/iteration7_decision_probe_20260518.py`.
- New result JSON: `artifacts/algorithm-exploration/iteration-7-decision-probe-20260518.json`.
- Iteration-specific report: `artifacts/algorithm-exploration/iteration-7-decision-gates-deepening-20260518.md`.
- Required prior outputs were read again: base proposal, verification plan, original probe JSON, and iterative log through iteration 6.

## A. Critique of previous conclusions

Iteration 6 finally added visual/contact-sheet evidence and actual paired-color pop metrics, but the conclusion was still too broad in three places.

1. The row recommendation said `quantile_max` is the next spike, but it did not yet define a promotion gate. Without an explicit gate, the recommendation can drift back into subjective “looks smoother” language. The missing conditions are:

```text
front_iou_delta_vs_current >= -0.005
side_iou_delta_vs_current  >= -0.005
z_jump_gt25_ratio          <= 0.01
direction_flip_ratio_mean  <= 0.01
projectionOnlyPointCount   = 0
```

These are deliberately not color gates. Iterations 3 and 6 showed color conflict is pair-dependent, so quantile should be accepted or rejected as a spatial/reveal-stability materialization first.

2. Directional color had only been checked on `goose+nubzuki`. That was weak because `goose+cake` has higher fixed-blend endpoint error and worse row-support mismatch. A basis that passes on one pair might fail pop thresholds on the harder pair.

3. The prior directional recommendation still allowed too many “acceptable alternatives.” Iteration 6 suggested `cosine_s1`, `softmax_tau035`, and sometimes `gaussian_sigma05`; however, implementation needs a default and a reject list. The missing condition is a provisional pass/fail table against actual paired colors:

```text
endpoint_rmse <= 0.25 * fixed_blend_endpoint_rmse
max_5deg_step_mean <= 0.04
max_5deg_step_pair_p99 <= 0.10
max_accel <= 0.01
wrong_lobe_endpoint <= 0.06
```

4. 3-view feasibility is now mathematically well constrained, but still has no positive path except co-designed assets. Further iteration should not spend more effort on arbitrary phoenix/kumdori top unless a jointly designed `C_target` is introduced.

## B. New concrete progress

I added and ran:

```text
python artifacts/.hermes/iteration7_decision_probe_20260518.py
```

It writes:

```text
artifacts/algorithm-exploration/iteration-7-decision-probe-20260518.json
```

The probe adds a decision-grade layer on top of iteration 6:

1. Row gate pass/fail for `quantile_max` vs `current_shuffled_max_reuse`.
2. Fixed-blend endpoint RMSE baseline for both pairs.
3. Directional basis pass/fail on both `goose+nubzuki` and `goose+cake` quantile pairs.
4. Explicit provisional thresholds for row and directional color promotion.

It remains a production-like PIL extraction proxy, not a browser-canvas parity result.

## C. Row materialization decision gate result

### goose + nubzuki

```text
current_shuffled_max_reuse:
  front_iou=0.837755, side_iou=0.799430
  z_jump_gt25_ratio=0.518373
  direction_flip_ratio_mean=0.657731
  color_conflict_mean=0.422893
  fixed_blend_endpoint_rmse_mean=0.211446

quantile_max:
  front_iou=0.837755, side_iou=0.799430
  z_jump_gt25_ratio=0.000000
  direction_flip_ratio_mean=0.000000
  color_conflict_mean=0.391630
  fixed_blend_endpoint_rmse_mean=0.195815

quantile_minus_current:
  front_iou_delta=0.000000
  side_iou_delta=0.000000
  z_jump_gt25_delta=-0.518373
  direction_flip_delta=-0.657731
  color_conflict_mean_delta=-0.031263

row gate: PASS
```

### goose + cake

```text
current_shuffled_max_reuse:
  front_iou=1.000000, side_iou=0.755999
  z_jump_gt25_ratio=0.679287
  direction_flip_ratio_mean=0.667049
  color_conflict_mean=0.480180
  fixed_blend_endpoint_rmse_mean=0.240090

quantile_max:
  front_iou=1.000000, side_iou=0.755999
  z_jump_gt25_ratio=0.000000
  direction_flip_ratio_mean=0.000000
  color_conflict_mean=0.480426
  fixed_blend_endpoint_rmse_mean=0.240213

quantile_minus_current:
  front_iou_delta=0.000000
  side_iou_delta=0.000000
  z_jump_gt25_delta=-0.679287
  direction_flip_delta=-0.667049
  color_conflict_mean_delta=+0.000246

row gate: PASS
```

Interpretation:
- `quantile_max` now passes a concrete promotion gate on both tested pairs.
- The goose+cake color conflict is slightly worse, but the gate intentionally does not require color improvement.
- The correct claim remains: `quantile_max` is a row-order/reveal-stability improvement with no measured projection cost in this proxy.

## D. Directional color decision gate result

### goose + nubzuki, quantile pairs

Fixed blend endpoint RMSE baseline:

```text
0.195815
```

Basis pass/fail:

```text
cosine_s1:
  endpoint_fraction=0.000000
  max_5deg_step_mean=0.031507
  p99_step=0.071634
  accel=0.004310
  wrong_lobe=0.000000
  gate=PASS

cosine_s2:
  endpoint_fraction=0.000000
  max_5deg_step_mean=0.034003
  p99_step=0.077309
  accel=0.005859
  wrong_lobe=0.000000
  gate=PASS

cosine_s8:
  max_5deg_step_mean=0.118556
  p99_step=0.269548
  accel=0.062691
  gate=FAIL

softmax_tau035:
  endpoint_fraction=0.108627
  max_5deg_step_mean=0.034127
  p99_step=0.077592
  accel=0.004747
  wrong_lobe=0.054313
  gate=PASS

gaussian_sigma05:
  endpoint_fraction=0.014281
  max_5deg_step_mean=0.052378
  p99_step=0.119087
  accel=0.010693
  gate=FAIL
```

### goose + cake, quantile pairs

Fixed blend endpoint RMSE baseline:

```text
0.240213
```

Basis pass/fail:

```text
cosine_s1:
  endpoint_fraction=0.000000
  max_5deg_step_mean=0.038650
  p99_step=0.068622
  accel=0.005287
  wrong_lobe=0.000000
  gate=PASS

cosine_s2:
  max_5deg_step_mean=0.041713
  gate=FAIL by the 0.04 step threshold

cosine_s8:
  max_5deg_step_mean=0.145436
  p99_step=0.258215
  accel=0.076905
  gate=FAIL

softmax_tau035:
  endpoint_fraction=0.108627
  max_5deg_step_mean=0.041865
  wrong_lobe=0.054313
  gate=FAIL by the 0.04 step threshold

gaussian_sigma05:
  max_5deg_step_mean=0.064254
  p99_step=0.114080
  accel=0.013118
  gate=FAIL
```

Interpretation:
- `cosine_s1` is now the only basis that passes both tested pairs under the provisional gates.
- `cosine_s2` and `softmax_tau035` are acceptable on goose+nubzuki but fail narrowly on goose+cake.
- `gaussian_sigma05` has good endpoints but fails smoothness/tail thresholds.
- `cosine_s8` should stay rejected as default; endpoint exactness is irrelevant if it pops.

## E. Updated mathematical recommendation

### Row materialization

Use `quantile_max` as the first implementation spike, not full OT/Sinkhorn.

Mathematically, for each row:

```text
N_y = max(|X_y|, |Z_y|)
x_k = Q_X((k+0.5)/N_y)
z_k = Q_Z((k+0.5)/N_y)
p_k = (x_k, y, z_k)
```

Acceptance should be stated as:

```text
projection coverage: non-regression vs current max+reuse
row continuity: large-jump and direction-flip ratios collapse near zero
projection-only/fallback points: forbidden / zero
color conflict: reported, not required to improve
```

This is a materialization/rounding result: it avoids fractional OT entirely while preserving the useful `max` mass policy. Full OT is now a later research option only if quantile cannot solve a specific measured artifact.

### Directional color

Use `cosine_s1` as the first shader basis candidate:

```text
w_F(theta) = cos(theta) / (cos(theta) + sin(theta))
w_R(theta) = sin(theta) / (cos(theta) + sin(theta))
c_i(theta) = w_F(theta)c_F_i + w_R(theta)c_R_i
```

for `theta in [0, 90deg]`, with clamped nonnegative cosine/sine in implementation.

Why this basis now wins:
- Endpoint exact on both tested pairs.
- Passes actual paired-color pop thresholds on both pairs.
- No endpoint leakage.
- No opacity or texture swap is required.

But the basis is still color-only. It cannot change support. The classifier from iteration 4 remains mandatory for morph cases:

```text
supportShiftEps = smallest eps such that both supports mutually cover after dilation.
0 px: color-only feasible
<=2 px: micro-displacement candidate
<=4 px: borderline research-only
>4 px: geometry-needed / defer
```

### 3-view

The exact 3-view condition and feasibility ladder remain unchanged, but the recommendation is now sharper:

```text
Do not implement arbitrary top view in production.
Do not spend near-term implementation time on phoenix/kumdori top adaptation.
Only revisit 3-view with co-designed assets whose top target is mostly inside S = union_y X_y × Z_y.
```

## F. Updated implementation spike order

1. Browser/Node canvas parity harness for extraction and row materialization.
2. JS throwaway implementation of `current_shuffled_max_reuse` vs `quantile_max` with the iteration-7 row gate.
3. If JS parity matches the PIL proxy, promote `quantile_max` as the first production candidate.
4. Directional color shader spike with `cosine_s1` only as default; use the iteration-7 directional gates and rendered mid-angle contact sheet.
5. Add angular support-difference classifier before any morph/micro-displacement work.
6. Keep 3-view research-only until co-designed assets pass row-support, coactivity, recognizability, visual-hull, and density gates.

## G. Open questions for next iteration

1. Browser parity remains the biggest verification gap. Re-run iteration-7 metrics with JS/canvas extraction rather than PIL.
2. The current row gate is metric-only. It should be paired with browser-rendered reveal frames to verify that `z_jump_gt25_ratio=0` actually reduces visible barcode/reveal chaos.
3. The directional gates are provisional and RGB/RMSE based. A rendered shader contact sheet should calibrate whether `max_5deg_step_mean <= 0.04` is too strict or too loose.
4. Test `cosine_s1` through the actual point shader with splat size/glow, because additive blending may change perceived color error.
5. Define a co-designed 3-view asset construction protocol if 3-view remains a product goal; arbitrary third images have been sufficiently falsified for now.
6. If this is the final iteration sequence, write the final one-hour recommendation around the now-stable order: `quantile_max` first, `cosine_s1` directional color second, 3-view/morph gated as research.

## H. Iteration 7 bottom line

- Strengthened: `quantile_max` now passes explicit row promotion gates on both tested pairs: no projection IoU loss, no large jumps, no direction flips.
- Refined: color conflict is not part of the quantile acceptance criterion; it is measured but pair-dependent.
- Strengthened: `cosine_s1` is the only directional basis that passes provisional gates on both `goose+nubzuki` and `goose+cake`.
- Rejected as defaults: `cosine_s8` and `gaussian_sigma05`; `cosine_s2`/`softmax_tau035` are no longer default because they fail or narrowly miss on the harder pair.
- Still uncertain: browser-canvas parity and actual shader-rendered contact sheets remain unresolved.

---

# Iteration 8 — rendered endpoint color + integer materialization certificate

Scope guard:
- Branch checked by tool: `algorithm-exploration-20260518`.
- Production files were not modified.
- New throwaway script: `artifacts/.hermes/iteration8_rendered_endpoint_and_rounding_probe_20260518.py`.
- New result JSON: `artifacts/algorithm-exploration/iteration-8-rendered-endpoint-and-rounding-probe-20260518.json`.
- Required prior outputs were read again: base proposal, verification plan, original probe JSON, and iterative log through iteration 7.

## A. 이전 결론 비판

Iteration 7의 결론은 방향은 맞지만 아직 세 군데가 얕다.

1. Directional color 평가는 point-pair 단위 endpoint RMSE였다. 실제 렌더에서는 같은 projection pixel에 여러 point가 누적/평균/가산될 수 있으므로, per-point endpoint가 낮아도 projection pixel 단위 색이 깨질 수 있다. 필요한 검증은 다음이다.

```text
For each projected pixel u:
  fixed_rendered(u) = aggregate_i blend(cF_i, cS_i), for points projecting to u
  directional_front(u) = aggregate_i cF_i
  directional_side(u)  = aggregate_i cS_i
  compare against target pixel color at u
```

2. `quantile_max`의 materialization/rounding 조건은 아직 명시적 증명 형태가 아니었다. full OT를 쓰지 않는다면 integer point 생성이 어떤 coverage와 multiplicity bound를 보장하는지 써야 한다.

3. fixed blend와 directional color 비교가 production-like blend 함수의 projection-pixel error로 정리되지 않았다. 특히 goose+cake처럼 color conflict가 높은 pair에서는 fixed blend의 projection-pixel endpoint error가 더 클 수 있으므로 shader spike의 효과 크기를 다시 확인해야 한다.

4. 여전히 browser/WebGL capture는 아니다. 이번 iteration도 PIL proxy이므로, 실제 canvas interpolation + additive splat + glow를 통과한 최종 색 검증은 남아 있다.

## B. 새로 만든 구체적 진전

새 throwaway probe를 추가/실행했다.

```text
python artifacts/.hermes/iteration8_rendered_endpoint_and_rounding_probe_20260518.py
```

결과:

```text
artifacts/algorithm-exploration/iteration-8-rendered-endpoint-and-rounding-probe-20260518.json
```

추가한 검증:

1. production-like fixed blend를 projection pixel 단위로 aggregate해서 target color와 비교.
2. directional endpoint가 projection pixel aggregate에서도 target을 회복하는지 측정.
3. `quantile_max`/current max-reuse의 integer materialization certificate:
   - matched row의 front/side active pixel coverage가 1.0인지
   - duplicate multiplicity spread가 row 내에서 `<=1`인지
   - duplicate p95/max를 projection view별로 기록

중요한 한계:
- 여전히 PIL proxy이며 browser canvas/WebGL splat capture가 아니다.
- projection key를 `(normalized row, px)`로 둔다. 같은 normalized row와 px에 서로 다른 원본 y 색이 섞이면 directional endpoint도 0이 아닐 수 있다. 이것은 실제 row normalization과 splat aggregation에서 생길 수 있는 색 혼합 위험을 드러내는 proxy다.

## C. Projection-pixel endpoint color 결과

### goose + nubzuki

```text
current_shuffled_max_reuse:
  front_fixed_rendered_rmse = 0.506556
  side_fixed_rendered_rmse  = 0.296367
  front_directional_endpoint_rmse ≈ 0
  side_directional_endpoint_rmse  ≈ 0
  front_fixed_err_p95 = 0.824157
  side_fixed_err_p95  = 0.498844

quantile_max:
  front_fixed_rendered_rmse = 0.480755
  side_fixed_rendered_rmse  = 0.265185
  front_directional_endpoint_rmse ≈ 0
  side_directional_endpoint_rmse  ≈ 0
  front_fixed_err_p95 = 0.641591
  side_fixed_err_p95  = 0.463473
```

해석:
- fixed blend는 projection pixel 단위로도 endpoint 색을 크게 훼손한다.
- directional endpoint는 aggregate 후에도 사실상 exact다.
- 이 pair에서는 quantile pairing이 fixed-blend rendered RMSE도 줄인다. 다만 이것은 pair-dependent라서 row materialization의 주된 acceptance 조건으로 삼으면 안 된다.

### goose + cake

```text
current_shuffled_max_reuse:
  front_fixed_rendered_rmse = 0.605884
  side_fixed_rendered_rmse  = 0.321409
  front_directional_endpoint_rmse ≈ 0
  side_directional_endpoint_rmse  = 0.019066

quantile_max:
  front_fixed_rendered_rmse = 0.616528
  side_fixed_rendered_rmse  = 0.326894
  front_directional_endpoint_rmse ≈ 0
  side_directional_endpoint_rmse  = 0.019066
```

해석:
- goose+cake에서는 quantile이 fixed-blend endpoint error를 약간 악화한다. 이것은 iteration 7의 “quantile은 color optimizer가 아니다”는 결론을 더 강하게 만든다.
- 그래도 directional endpoint는 side 기준 약 94.17% RMSE reduction을 보인다.
- side directional RMSE가 0이 아닌 이유는 same normalized row/projection bucket에 서로 다른 source-y 색이 섞이는 proxy aggregation 때문이다. 실제 WebGL splat에서도 중복/row normalization으로 색이 섞일 수 있으므로, shader contact sheet에서 확인해야 할 리스크다.

## D. Integer materialization / rounding certificate

`N_y=max(|X_y|,|Z_y|)`와 quantile index

```text
x_k = X_sorted[floor((k+0.5)|X_y|/N_y)]
z_k = Z_sorted[floor((k+0.5)|Z_y|/N_y)]
```

를 쓰면 matched row에서 다음 성질을 실험적으로 확인했다.

```text
all_matched_front_pixels_covered = true
all_matched_side_pixels_covered  = true
front_multiplicity_spread_lte1   = true
side_multiplicity_spread_lte1    = true
```

두 pair 모두 동일하게 통과했다.

```text
goose+nubzuki:
  matched rows = 120
  front coverage min = 1.0
  side coverage min  = 1.0
  front multiplicity spread max = 1
  side multiplicity spread max  = 1
  front duplicate p95 = 8, max = 10
  side duplicate p95  = 2, max = 6

goose+cake:
  matched rows = 144
  front coverage min = 1.0
  side coverage min  = 1.0
  front multiplicity spread max = 1
  side multiplicity spread max  = 1
  front duplicate p95 = 10, max = 20
  side duplicate p95  = 1, max = 3
```

주의: modulo max-reuse도 multiplicity spread 자체는 `<=1`일 수 있다. quantile의 핵심 이점은 multiplicity fairness가 아니라 monotone spatial order다. 즉 promotion gate는 다음처럼 분리해야 한다.

```text
coverage/fairness gate:
  all matched-row pixels covered
  duplicate spread <= 1

continuity gate:
  z_jump_gt25_ratio <= 0.01
  direction_flip_ratio_mean <= 0.01
```

Modulo는 전자를 통과할 수 있지만 후자에서 실패한다. Quantile은 둘 다 통과한다.

## E. 업데이트된 추천

1. Row materialization:
   - `quantile_max` 추천은 유지한다.
   - 단, 이유를 “color improvement”가 아니라 “same max-mass coverage + fair integer rounding + monotone row order”로 고정해야 한다.
   - full OT/Sinkhorn은 여전히 다음 단계가 아니다. 현재까지는 fractional transport보다 deterministic quantile rounding이 더 단순하고 검증 가능하다.

2. Directional color:
   - `cosine_s1` 추천은 더 강해졌다.
   - point-pair RMSE뿐 아니라 projection-pixel aggregate proxy에서도 fixed blend endpoint error가 매우 크고, directional endpoint가 크게 개선된다.
   - 하지만 실제 splat/glow/additive blending에서는 endpoint exact가 깨질 수 있으므로 browser-rendered contact sheet가 다음 blocker다.

3. 3-view:
   - 이번 iteration은 3-view를 더 파지 않았다. 이전 iteration 2–5에서 arbitrary phoenix/kumdori top은 충분히 falsify되었다.
   - 3-view는 co-designed asset protocol이 생기기 전까지 research-only로 유지하는 편이 맞다.

## F. Open questions for next iteration

1. Browser/Node canvas parity: PIL proxy 대신 actual canvas extraction으로 iteration 7–8 metrics를 재실행해야 한다.
2. WebGL shader contact sheet: fixed blend vs `cosine_s1` directional color를 실제 point shader/splat/glow에서 capture해야 한다.
3. Projection-pixel aggregate metric을 실제 렌더 방식에 맞게 정의해야 한다. 평균, alpha composite, additive clamp 중 production shader와 가장 가까운 모델을 선택해야 한다.
4. Quantile row order가 실제 reveal-frame barcode/noise를 줄이는지 browser-rendered reveal frame으로 확인해야 한다.
5. Directional color의 support limit는 여전히 남는다. support-difference classifier를 actual intermediate targets에 적용해야 한다.
6. Co-designed 3-view asset protocol이 필요하다면 `C_target`을 먼저 `S=union_y X_y×Z_y` 안에서 디자인하고 recognizability threshold를 통과하는지 봐야 한다.

## G. Iteration 8 bottom line

- Strengthened: `quantile_max`는 integer materialization 관점에서 matched-row coverage와 multiplicity fairness를 보장하면서, 기존 iteration의 continuity gate까지 통과하는 가장 단순한 후보로 정리됐다.
- Refined: modulo도 multiplicity fairness는 통과할 수 있으므로, quantile의 진짜 차별점은 monotone row order/reveal stability다.
- Strengthened: directional color는 projection-pixel endpoint proxy에서도 fixed blend보다 훨씬 강하다. `cosine_s1` shader spike의 우선순위가 올라간다.
- Still uncertain: browser-canvas parity와 실제 WebGL splat/glow contact sheet는 여전히 마지막 큰 검증 공백이다.


---

# Iteration 9 — color-only support 판정법 + low-pop directional basis 보강

Scope guard:
- Branch checked: `algorithm-exploration-20260518`.
- Production 파일은 수정하지 않았다.
- 새 throwaway script: `artifacts/.hermes/iteration9_support_and_basis_probe_20260518.py`.
- 새 result JSON: `artifacts/algorithm-exploration/iteration-9-support-and-basis-probe-20260518.json`.
- 이번 iteration에서 다시 확인한 기존 산출물: base proposal, verification plan, original probe JSON, iterative log, iteration 8 report.

## A. 이전 결론 비판

Iteration 8까지의 결론은 `quantile_max + cosine_s1 directional color`를 가장 유력한 spike로 압축한 점이 좋다. 하지만 아직 얕은 부분이 남아 있다.

1. Directional color가 endpoint 색을 회복한다는 사실과, angular morph가 색만으로 가능한지는 별개다. 기존 로그는 “silhouette support가 바뀌면 geometry-needed”라고 말했지만, 이를 실제 reference mask에서 판정하는 수식/metric이 부족했다.

2. `cosine_s1` 추천은 pop metric이 낮다는 이유가 있었지만, 후보 basis의 요구조건이 shader promotion rule로 충분히 정리되지 않았다. 특히 endpoint-exact, monotone, max jump, acceleration을 동시에 보는 기준이 필요하다.

3. 실제 이미지를 쓰지 않은 약점은 여전히 남아 있다. Iteration 8은 actual reference color를 썼지만 PIL projection proxy였고, 이번에도 browser/WebGL splat capture가 아니다. 따라서 이번 결과는 “필요조건 판정”이지 최종 visual proof가 아니다.

4. Angular morph 실험 계획은 있었지만, “색-only로 가능한 경우”와 “geometry/micro-displacement가 필요한 경우”를 QA가 자동으로 분류하는 형태가 아니었다. 다음 구현 spike가 scope creep 없이 진행되려면 이 classifier가 먼저 필요하다.

## B. 새로 만든 구체적 진전

새 probe를 작성/실행했다.

```text
python artifacts/.hermes/iteration9_support_and_basis_probe_20260518.py
```

이 probe는 실제 reference image alpha/non-white mask를 `160×120` proxy로 읽고 다음을 계산한다.

1. Color-only/material-only support 판정:

```text
Given fixed projected support Sθ and target support Tθ:
  create_missing = |Tθ \ Sθ|
  erase_needed   = |Sθ \ Tθ|

color-only pass if:
  create_missing / |Tθ| <= 0.01
  erase_needed   / |Sθ| <= 0.01
```

해석:
- `Tθ \ Sθ`는 기존 점 support 밖에 새 foreground를 만들어야 하는 영역이다. 색만으로는 불가능하다.
- `Sθ \ Tθ`는 기존 foreground를 지워야 하는 영역이다. background-colored paint나 alpha-to-zero로 해결하면 opacity gate/cheat 위험이다.
- 따라서 둘 중 하나가 1%를 넘으면 pure directional color가 아니라 micro-displacement 또는 geometry-needed로 분류한다.

2. 실제 reference mask의 shift stress test:
- `goose`, `nubzuki`, `cake`, `phoenix`, `kumdori` mask를 1/2/4/8/12 px 수평 또는 1/2/4/8 px 수직 이동시킨 target과 비교.
- 목적은 “팔/외곽선이 몇 px 움직이면 색-only가 깨지는가”를 수치화하는 것이다.

3. Fixed-view asset support incompatibility:
- `goose -> nubzuki/cake/phoenix/kumdori`를 같은 view support에서 color-only로 바꾸려 할 때 필요한 missing/erase ratio를 계산.
- 이것은 endpoint asset swap을 색만으로 하자는 뜻이 아니라, support mismatch가 얼마나 큰지 보여주는 필요조건 probe다.

4. Directional weight basis 재비교:
- `linear`, `smoothstep`, `smootherstep`, `cosine_s1`, `cosine_s2`, `cosine_s8`를 endpoint leakage, linear path RMSE, max 5° jump, acceleration, monotonicity로 비교.

## C. 실행 결과 요약

### 1. Goose mask shift: 2 px도 color-only로는 이미 실패

```text
goose right_2px:
  create_missing_ratio_vs_target = 0.210054
  erase_ratio_vs_base            = 0.210054
  IoU                            = 0.652819
  geometry_needed_if_no_opacity_gate = true

goose right_4px:
  create_missing_ratio_vs_target = 0.381807
  erase_ratio_vs_base            = 0.381807
  IoU                            = 0.447380

goose right_8px:
  create_missing_ratio_vs_target = 0.562537
  erase_ratio_vs_base            = 0.562537
  IoU                            = 0.279969

goose down_4px:
  create_missing_ratio_vs_target = 0.516457
  erase_ratio_vs_base            = 0.516457
  IoU                            = 0.318863
```

해석:
- 얇은 limb 하나가 아니라 전체 mask shift라서 stress test가 강한 편이지만, 핵심은 분명하다. contour/support가 조금만 이동해도 pure color-only는 빠르게 실패한다.
- “팔이 움직인다”가 실제 silhouette 이동이면 `cosine_s1` shader로 해결할 문제가 아니다. micro-displacement 후보로도 2~4 px bound를 넘는 영역 비율을 따져야 한다.

### 2. Asset support mismatch는 color-only로 불가능

```text
goose -> nubzuki:
  missing_ratio = 0.749360
  erase_ratio   = 0.238181
  IoU           = 0.232427
  geometry_needed = true

goose -> cake:
  missing_ratio = 0.843284
  erase_ratio   = 0.011969
  IoU           = 0.156419
  geometry_needed = true

goose -> phoenix:
  missing_ratio = 0.911604
  erase_ratio   = 0.427887
  IoU           = 0.082914
  geometry_needed = true

goose -> kumdori:
  missing_ratio = 0.855198
  erase_ratio   = 0.000598
  IoU           = 0.144789
  geometry_needed = true
```

해석:
- Directional color는 endpoint color conflict를 해결하는 기술이지, 서로 다른 silhouette support를 같은 camera support에서 만들어내는 기술이 아니다.
- 현재 2-view illusion이 가능한 이유는 front/right가 서로 다른 projection 축을 쓰기 때문이다. 같은 projection support에서 asset을 바꾸려면 새 foreground 생성/삭제가 필요해진다.

### 3. Basis 비교: sharp lobe는 pop 때문에 계속 reject

```text
linear:
  endpoint leakage = 0 / 0
  linear_path_rmse = 0.000000
  max_5deg_jump    = 0.055556
  max_5deg_accel   ≈ 0
  monotone         = true

cosine_s1:
  endpoint leakage = 0 / 0
  linear_path_rmse = 0.031562
  max_5deg_jump    = 0.080450
  max_5deg_accel   = 0.011004
  monotone         = true

smoothstep:
  endpoint leakage = 0 / 0
  linear_path_rmse = 0.067159
  max_5deg_jump    = 0.082990
  max_5deg_accel   = 0.016461
  monotone         = true

smootherstep:
  endpoint leakage = 0 / 0
  linear_path_rmse = 0.101257
  max_5deg_jump    = 0.103313
  max_5deg_accel   = 0.017623
  monotone         = true

cosine_s8:
  endpoint leakage = 0 / 0
  linear_path_rmse = 0.216266
  max_5deg_jump    = 0.302724
  max_5deg_accel   = 0.160076
  monotone         = true
```

업데이트된 basis rule:

```text
Accept candidate basis only if:
  endpoint leakage == 0 or explicitly bounded <= 0.05
  monotone between canonical views
  max_5deg_weight_jump <= ~0.10 before visual tuning
  max_5deg_accel <= ~0.02 before visual tuning
  no alpha-to-zero / no opacity gate
```

이 기준에서는 `cosine_s1`, `linear`, `smoothstep`, `smootherstep`가 후보이고, `cosine_s8`은 중간각 pop 위험 때문에 reject다. 단, shader material 해석을 생각하면 `linear`는 물리 BRDF라기보다 interpolation curve에 가까우므로, implementation spike 1순위는 여전히 `cosine_s1`, 비교군은 `smoothstep/smootherstep`가 맞다.

## D. 업데이트된 추천

1. Row materialization:
   - Iteration 8의 결론 유지: `quantile_max`를 첫 구현 spike로 둔다.
   - 이유는 color 최적화가 아니라 coverage/fair integer materialization/monotone row order다.

2. Directional color:
   - `cosine_s1` 우선 추천 유지.
   - 단, shader spike에는 이번 iteration의 basis gate를 반드시 넣는다: endpoint leakage, max 5° jump, acceleration, monotonicity.
   - `smoothstep/smootherstep`는 물리성은 약하지만 pop 비교군으로 contact sheet에 포함할 가치가 있다.

3. Angular morph:
   - pure color-only 가능 여부는 support classifier로 먼저 판정한다.
   - `create_missing_ratio` 또는 `erase_ratio`가 1%를 넘으면 color-only가 아니라 geometry-needed로 기록한다.
   - micro-displacement는 2~4 px bound 안에서 canonical endpoint displacement=0을 만족할 때만 research 후보로 둔다.

4. 3-view:
   - 이번 iteration은 3-view graph를 더 실행하지 않았다. 기존 iteration 2–5의 결론 유지: arbitrary third image는 실패했고, co-designed `C ⊆ ⋃_y X_y×Z_y` protocol 없이는 production 금지.

## E. 남은 불확실성 / 다음 iteration open questions

1. Browser/WebGL capture: PIL proxy가 아니라 실제 splat/glow/additive shader에서 `cosine_s1` vs fixed blend contact sheet를 찍어야 한다.
2. 실제 intermediate target이 필요하다. 이번 shift test는 stress test일 뿐, 사용자가 원하는 “팔 움직임” 이미지/시퀀스가 있으면 support classifier를 그 target에 직접 적용해야 한다.
3. Micro-displacement solver는 아직 없다. support diff가 1%를 넘는 경우, 그 diff가 작은 boundary displacement로 설명되는지 아니면 새 topology/limb 생성인지 구분하는 matching metric이 필요하다.
4. Quantile row order가 reveal-frame visual artifact를 실제로 줄이는지는 rendered reveal frame에서 확인해야 한다.
5. Directional basis threshold(`jump <= 0.10`, `accel <= 0.02`)는 perceptual calibration 전 임시 기준이다. contact sheet에서 눈으로 pop threshold를 보정해야 한다.

## F. Iteration 9 bottom line

- 새로 강화된 점: “색-only 가능/불가능”을 support set 조건으로 명확히 판정했다. 색 basis는 기존 support 안의 RGB를 바꾸는 도구이고, foreground 생성/삭제는 geometry 또는 opacity-gate 문제다.
- 실제 reference mask 기반 stress test에서 2 px silhouette shift도 missing/erase ratio가 21%로 커져 color-only는 실패한다는 필요한 경고를 얻었다.
- Basis 선택은 `cosine_s1` 유지. `cosine_s8` 같은 sharp lobe는 endpoint가 맞아도 5° jump/accel 때문에 reject한다.
- 남은 최대 공백은 actual WebGL rendered contact sheet와 실제 intermediate target에 대한 support classifier 적용이다.


---

# Iteration 10 — localized morph displacement lower-bound

Scope guard:
- Branch checked by tool: `algorithm-exploration-20260518`.
- Production 파일은 수정하지 않았다.
- 새 throwaway script: `artifacts/.hermes/iteration10_local_morph_displacement_probe_20260518.py`.
- 새 result JSON: `artifacts/algorithm-exploration/iteration-10-local-morph-displacement-probe-20260518.json`.
- 이번 iteration에서 다시 읽은 필수 산출물: base proposal, verification plan, original probe JSON, iterative log through iteration 9.

## A. 이전 결론 비판

Iteration 9는 color-only 가능/불가능을 support set 조건으로 정리한 점이 좋았다. 하지만 아직 얕은 부분이 있었다.

1. Whole-object shift stress test가 너무 강했다. `goose` 전체를 2px 움직이면 create/erase ratio가 크게 나오는 것은 당연하다. 실제 요구는 “팔/외곽선 일부가 움직임”일 가능성이 높으므로 localized support shift를 따로 봐야 한다.

2. `color-only 실패`와 `geometry-needed` 사이가 너무 거칠었다. 색만으로 안 된다고 바로 완전 geometry 재구성으로 가면 과하다. 필요한 중간 판정은 다음이다.

```text
create_missing = T \ S
erase_needed   = S \ T
D_create = distance(create_missing pixels, S)
D_erase  = distance(erase_needed pixels, T)

pure color-only: create/target <= 1% and erase/base <= 1%
micro-displacement candidate: changed pixels are local and nearest-support distance is small
geometry-needed/defer: changed area is large or nearest-support distance tail is large
```

3. Micro-displacement feasibility에는 “몇 px 움직이면 되는가”뿐 아니라 “얼마나 많은 support가 바뀌는가”가 필요하다. 작은 거리라도 전체 object의 20~30%가 바뀌면 physical point invariant가 약해진다.

4. 여전히 실제 intermediate target이 없다. 이번도 synthetic localized shift라서 필요조건/분류기 검증이지, 제품 target에 대한 pass/fail은 아니다.

## B. 새로 만든 구체적 진전

새 probe를 작성/실행했다.

```text
python artifacts/.hermes/iteration10_local_morph_displacement_probe_20260518.py
```

결과 파일:

```text
artifacts/algorithm-exploration/iteration-10-local-morph-displacement-probe-20260518.json
```

Probe 내용:

1. 실제 `goose.png` reference mask를 `160×120` proxy로 읽는다.
2. 전체 object shift와 localized right-tail shift를 비교한다.
3. Localized region은 goose support의 rightmost 25% x-quantile이다.
4. 각 target에 대해 다음을 계산한다.

```text
create_missing_ratio_vs_target
erase_ratio_vs_base
symmetric_diff_ratio_vs_union
IoU
create/erase/symdiff nearest-support distance p50/p95
component_count / largest_component_ratio
morph_classification
```

분류 rule:

```text
color_only_feasible:
  create_missing_ratio <= 0.01 and erase_ratio <= 0.01

micro_displacement_candidate_strong:
  symdiff_distance_p95 <= 2px and symmetric_diff_ratio_vs_union <= 0.15

micro_displacement_candidate_borderline:
  symdiff_distance_p95 <= 4px and symmetric_diff_ratio_vs_union <= 0.30

geometry_needed_or_defer:
  otherwise
```

이 rule은 production rule이 아니라 다음 spike를 막기 위한 연구용 gate다.

## C. 실행 결과

Base goose:

```text
goose_base_pixels = 2261
goose_right_tail_pixels = 571
right_tail_region ≈ base support의 25.25%
```

### 1. Whole-object shift와 localized shift는 다르게 판정된다

Whole-object horizontal shift:

```text
right_2px:
  create=0.0964, erase=0.0964, IoU=0.8241
  symdiff_distance_p95=2.0
  class=micro_displacement_candidate_borderline

right_4px:
  create=0.1592, erase=0.1592, IoU=0.7253
  symdiff_distance_p95=4.0
  class=micro_displacement_candidate_borderline

right_8px:
  create=0.2946, erase=0.2946, IoU=0.5449
  symdiff_distance_p95=7.0
  class=geometry_needed_or_defer
```

Localized right-tail shift:

```text
right_tail_2px:
  create=0.0606, erase=0.0606, symdiff=0.1143, IoU=0.8857
  symdiff_distance_p95=2.0
  class=micro_displacement_candidate_strong

right_tail_4px:
  create=0.1092, erase=0.1092, symdiff=0.1970, IoU=0.8030
  symdiff_distance_p95=3.606
  class=micro_displacement_candidate_borderline

right_tail_8px:
  create=0.1849, erase=0.1849, symdiff=0.3121, IoU=0.6879
  symdiff_distance_p95=6.479
  class=geometry_needed_or_defer

right_tail_down_4px:
  create=0.0584, erase=0.0584, symdiff=0.1103, IoU=0.8897
  symdiff_distance_p95=3.606
  class=micro_displacement_candidate_borderline
```

해석:
- Iteration 9의 “2px shift도 color-only 실패”는 유지된다. 2px localized shift도 create/erase가 1%를 넘기므로 pure color-only는 아니다.
- 하지만 localized 2px는 whole-object 2px보다 훨씬 좋은 micro-displacement 후보다. 바뀐 support가 union의 11.4%이고 p95 distance가 2px라서 bounded micro-displacement 연구 대상으로 분류할 수 있다.
- 4px localized shift는 borderline이다. physical plausibility와 canonical endpoint 보존을 실제 renderer에서 검증해야 한다.
- 8px localized shift는 바뀐 영역과 거리 tail이 커져 geometry-needed/defer로 보는 편이 안전하다.

### 2. Asset support mismatch는 여전히 geometry-needed

```text
goose -> nubzuki:
  create=0.5510, erase=0.1614, IoU=0.4133
  class=geometry_needed_or_defer

goose -> cake:
  create=0.7295, erase=0.0000, IoU=0.2705
  class=geometry_needed_or_defer

goose -> phoenix:
  create=0.7931, erase=0.3357, IoU=0.1873
  class=geometry_needed_or_defer

goose -> kumdori:
  create=0.6976, erase=0.0097, IoU=0.3015
  class=geometry_needed_or_defer
```

해석:
- Same projection에서 asset을 바꾸는 것은 directional color 문제가 아니다.
- 현재 2-view illusion은 서로 다른 projection 축을 사용하기 때문에 가능하다. 같은 projection support에서 goose를 nubzuki/cake/phoenix/kumdori로 바꾸려면 foreground 생성/삭제가 너무 크다.

## D. 업데이트된 수학적 판정법

Iteration 10은 angular morph 판정 ladder를 다음처럼 보강한다.

```text
Input:
  S = current projected support at angle theta
  T = desired target support at angle theta

Step 1. color-only support gate
  create = |T \ S| / |T|
  erase  = |S \ T| / |S|
  if create <= 0.01 and erase <= 0.01:
    color-only feasible

Step 2. displacement lower-bound gate
  d_create_p95 = p95 distance from T\S to S
  d_erase_p95  = p95 distance from S\T to T
  d_sym_p95    = p95 union of those distances
  changed_ratio = |S xor T| / |S union T|

Step 3. classification
  if d_sym_p95 <= 2 and changed_ratio <= 0.15:
    micro-displacement candidate, strong
  elif d_sym_p95 <= 4 and changed_ratio <= 0.30:
    micro-displacement candidate, research-only/borderline
  else:
    geometry-needed/defer
```

중요한 점:
- 이 distance는 실제 point matching solver의 충분조건이 아니다. lower-bound/triage metric이다.
- canonical endpoint에서는 displacement가 0이어야 한다.
- micro-displacement가 허용되더라도 alpha-to-zero나 projection-only point를 추가하면 안 된다.

## E. 업데이트된 추천

1. Row materialization:
   - 기존 결론 유지: `quantile_max`가 첫 구현 spike다.
   - 이유는 coverage/fair integer materialization/monotone row order이며, color optimization으로 팔면 안 된다.

2. Directional color:
   - 기존 결론 유지: `cosine_s1`가 첫 shader basis 후보다.
   - 단, 이번 iteration이 다시 확인한 대로 color basis는 support를 만들거나 지우지 않는다.

3. Angular morph:
   - pure color-only gate를 먼저 적용한다.
   - 실패하면 바로 production 구현하지 말고 displacement lower-bound gate를 적용한다.
   - localized 2px급 변화는 micro-displacement 연구 후보가 될 수 있다.
   - localized 4px급 변화는 borderline/research-only다.
   - 8px급 또는 asset-swap급 support 변화는 geometry-needed/defer다.

4. 3-view:
   - 이번 iteration도 arbitrary top을 더 파지 않았다. Iteration 2–5의 rejection은 유지한다.
   - 3-view는 co-designed `C ⊆ ⋃_y X_y×Z_y` protocol과 recognizability gate 없이는 production 금지다.

## F. 남은 불확실성 / 다음 iteration open questions

1. 실제 intermediate target이 필요하다. 이번 localized right-tail shift는 proxy이며, 사용자가 원하는 팔/외곽선 움직임 target에 classifier를 직접 적용해야 한다.
2. Micro-displacement solver가 아직 없다. 다음 연구는 changed support pixel을 기존 points에 매칭하고 `max/mean displacement`, canonical endpoint damage, temporal smoothness를 함께 재야 한다.
3. Browser/WebGL rendered contact sheet가 여전히 없다. `quantile_max` row order와 `cosine_s1` directional color를 실제 splat/glow에서 캡처해야 한다.
4. Displacement thresholds는 아직 provisional이다. 2px/4px 기준이 실제 카메라 distance, point size, glow scale에 따라 달라진다.
5. Localized region selection을 실제 semantic limb/part mask로 바꿔야 한다. Rightmost 25%는 임시 proxy다.

## G. Iteration 10 bottom line

- 새로 강화된 점: angular morph를 `color-only`, `micro-displacement candidate`, `geometry-needed/defer`로 나누는 distance-based lower-bound gate를 추가했다.
- 실제 reference mask 기반 localized test에서 right-tail 2px shift는 pure color-only는 아니지만 micro-displacement strong candidate로 분류됐다.
- 4px localized shift는 borderline, 8px localized shift는 geometry-needed/defer다.
- Asset support swap은 여전히 geometry-needed다.
- 전체 추천은 안정적이다: near-term은 `quantile_max` + `cosine_s1`; morph/3-view는 gate를 통과한 경우에만 research로 진행한다.

---

## Iteration 11 — endpoint-zero micro-displacement gate deepening

### A. 이전 결론 비판

Iteration 10의 `color-only / micro-displacement candidate / geometry-needed` 분류는 유효하지만, 아직 세 가지가 얕았다.

1. `distance p95 <= 2/4px`는 lower-bound일 뿐, canonical endpoint를 보존하는 displacement 함수 조건이 빠져 있었다.
2. `micro-displacement candidate`가 실제로 어떤 수식으로 구현될 수 있는지 불명확했다. 최소한 `p_i(theta)=p_i0+d_i*b(theta)`와 `b(0)=b(90)=0` 같은 endpoint-zero 조건이 필요하다.
3. 중간각 pop/smoothness metric이 없었다. 같은 4px 변화라도 5° step마다 얼마나 튀는지 따로 재야 한다.
4. 실제 intermediate product target은 여전히 없다. 이번도 실제 goose reference image 기반 synthetic localized target이므로 제품 pass/fail이 아니라 gate 강화다.

### B. 새로 만든 구체적 진전

새 throwaway probe를 작성/실행했다.

```text
python artifacts/.hermes/iteration11_endpoint_zero_displacement_probe_20260518.py
```

결과 파일:

```text
artifacts/algorithm-exploration/iteration-11-endpoint-zero-displacement-probe-20260518.json
artifacts/algorithm-exploration/iteration-11-endpoint-zero-displacement-deepening-20260518.md
```

Endpoint-zero morph basis를 gate에 추가했다.

```text
p_i(theta) = p_i0 + d_i * b(theta)
b(theta) = sin(2theta), theta in [0°, 90°]
b(0°)=0, b(90°)=0, b(45°)=1
```

이 basis는 front/right canonical endpoint에서는 displacement를 0으로 만들고, 중간각에서만 최대 displacement를 허용한다. Production 추천이 아니라 micro-displacement research spike의 최소 조건이다.

Probe metric:

```text
create_ratio_vs_target = |T \ S| / |T|
erase_ratio_vs_base    = |S \ T| / |S|
symdiff_ratio_vs_union = |S xor T| / |S union T|
nearest-support p95/max
endpoint-zero max_5deg_displacement_jump
moved_region_ratio
```

분류 rule:

```text
color_only_feasible:
  create <= 1% and erase <= 1%

endpoint_zero_micro_displacement_strong_candidate:
  p95 <= 2px
  changed_ratio <= 15%
  moved_region_ratio <= 30%
  max_5deg_jump <= 0.4px

endpoint_zero_micro_displacement_borderline_research_only:
  p95 <= 4px
  changed_ratio <= 30%
  moved_region_ratio <= 35%
  max_5deg_jump <= 0.8px

geometry_needed_or_defer:
  otherwise
```

### C. 실행 결과

실제 `artifacts/reference-image/goose.png`를 160×120 proxy mask로 읽었다.

```text
base_pixels = 1675
right_tail_quantile_x_min = 98
right_tail_pixels = 449
right_tail_ratio_vs_base = 0.26806
```

핵심 결과:

```text
right_tail_right_1px:
  create=0.038806, erase=0.038806, symdiff=0.074713, IoU=0.925287
  nearest p95=1px, endpoint max_5deg_jump=0.1736px
  class=endpoint_zero_micro_displacement_strong_candidate

right_tail_right_2px:
  create=0.068657, erase=0.068657, symdiff=0.128492, IoU=0.871508
  nearest p95=2px, endpoint max_5deg_jump=0.3473px
  class=endpoint_zero_micro_displacement_strong_candidate

right_tail_right_4px:
  create=0.124179, erase=0.124179, symdiff=0.220924, IoU=0.779076
  nearest p95=4px, endpoint max_5deg_jump=0.6946px
  class=endpoint_zero_micro_displacement_borderline_research_only

right_tail_down_2px:
  create=0.063881, erase=0.063881, symdiff=0.120090, IoU=0.879910
  nearest p95=2px, endpoint max_5deg_jump=0.3473px
  class=endpoint_zero_micro_displacement_strong_candidate

right_tail_down_4px:
  create=0.106866, erase=0.106866, symdiff=0.193096, IoU=0.806904
  nearest p95=4px, endpoint max_5deg_jump=0.6946px
  class=endpoint_zero_micro_displacement_borderline_research_only

right_tail_diag_2_2px:
  create=0.084776, erase=0.084776, symdiff=0.156302, IoU=0.843698
  create nearest p95=2.8284px, endpoint max_5deg_jump=0.4912px
  class=endpoint_zero_micro_displacement_borderline_research_only

right_tail_diag_4_2px:
  create=0.124776, erase=0.124776, symdiff=0.221868, IoU=0.778132
  create nearest p95=4.1231px, endpoint max_5deg_jump=0.7766px
  class=geometry_needed_or_defer
```

해석:

1. 1~2px localized tail motion도 create/erase가 1%를 넘기므로 pure color-only가 아니다.
2. 2px motion은 endpoint-zero basis에서 5° step jump가 0.3473px라서 temporal pop 관점에서는 strong research candidate다.
3. 4px horizontal/down motion은 p95와 jump는 bound 안이지만 changed support가 19~22%이고 IoU가 0.78~0.81이므로 borderline research-only다.
4. Diagonal motion은 vector magnitude 때문에 더 위험하다. 2px+2px도 borderline, 4px+2px는 geometry-needed/defer다.
5. moved region이 base의 26.8%라서 “작은 local limb”로 보기엔 크다. 실제 semantic part mask가 더 작으면 결과가 달라질 수 있다.

### D. 업데이트된 수학적 판정법

Angular morph gate를 다음 순서로 갱신한다.

```text
1. Color-only support gate:
   if |T\S|/|T| <= 0.01 and |S\T|/|S| <= 0.01:
     color/material-only candidate

2. Displacement lower-bound gate:
   d95 = max(p95_distance(T\S -> S), p95_distance(S\T -> T))
   changed = |S xor T| / |S union T|
   moved_region = estimated affected source support ratio

3. Endpoint-zero basis gate:
   choose b(theta) with b(canonical_angles)=0
   for 2-view front/right orbit, initial probe b(theta)=sin(2theta)
   jump = max_theta ||d|| * |b(theta+step)-b(theta)|

4. Classification:
   strong if d95 <= 2px, changed <= 0.15, moved_region <= 0.30, jump <= 0.4px/5deg
   borderline if d95 <= 4px, changed <= 0.30, moved_region <= 0.35, jump <= 0.8px/5deg
   otherwise geometry-needed/defer
```

주의: 이 gate는 충분조건이 아니다. 실제 renderer에서 point size/glow/occlusion, right projection coupling, reveal artifact를 봐야 한다.

### E. 업데이트된 추천

1. Near-term production 후보는 계속 `quantile_max row materialization` + `cosine_s1 directional color`다.
2. Morph는 production 후보가 아니라 research-only spike다.
3. Morph를 검토하려면 먼저 actual intermediate target mask에 이번 gate를 적용한다.
4. Strong이면 endpoint-zero basis throwaway renderer로 넘어간다.
5. Borderline이면 contact sheet와 canonical endpoint damage를 본 뒤 보류/폐기한다.
6. Geometry-needed면 micro-displacement로 포장하지 말고 geometry/asset redesign 문제로 분류한다.

### F. 남은 불확실성 / 다음 iteration open questions

1. 실제 intermediate target mask가 필요하다. Goose right-tail proxy는 제품 요구의 팔/외곽선 변화와 다를 수 있다.
2. `sin(2theta)`는 2-view 0°/90° orbit용이다. 3-view나 45° overhead reveal에서는 canonical-zero 다점 basis를 다시 설계해야 한다.
3. Probe는 2D support만 본다. 실제 3D point가 front x/y로 움직일 때 right/reveal projection coupling이 어떻게 깨지는지 재야 한다.
4. Semantic limb/part mask가 필요하다. rightmost 25%는 임시 proxy다.
5. WebGL splat contact sheet가 아직 없다. point size/glow가 1~2px displacement를 숨기는지 또는 더 튀게 만드는지 확인해야 한다.

### G. Iteration 11 bottom line

- 새로 강화된 점: micro-displacement gate에 `endpoint-zero basis`, `per-frame jump`, `changed support ratio`, `moved region ratio`를 추가했다.
- 실제 goose mask proxy에서 right-tail 2px 이동은 color-only는 아니지만 endpoint-zero micro-displacement strong research candidate다.
- 4px 이동은 borderline research-only, diagonal 4px+2px는 geometry-needed/defer다.
- 최종 추천은 변하지 않는다. Production은 row materialization과 directional color를 먼저 검증하고, morph는 실제 intermediate target이 gate를 통과할 때만 throwaway로 진행한다.
