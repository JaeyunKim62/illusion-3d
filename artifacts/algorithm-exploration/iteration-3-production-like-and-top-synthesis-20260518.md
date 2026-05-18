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
