# Iteration 4 — feasibility ladder + angular morph support test

Scope guard:
- Branch checked by tool: `algorithm-exploration-20260518`.
- Production files were not modified.
- New throwaway script: `artifacts/.hermes/iteration4_feasibility_ladder_and_morph_probe_20260518.py`.
- New result JSON: `artifacts/algorithm-exploration/iteration-4-feasibility-ladder-and-morph-probe-20260518.json`.
- Prior required outputs were read again: base proposal, verification plan, original probe JSON, and iterative log through iteration 3.

## 1. Critique of previous conclusion

Iteration 3 was useful but still had shallow spots.

1. It reported the 2-view row-overlap cap indirectly. The missing formal gate is:

```text
U_A = {(x,y) in A : Z_y is non-empty}
U_B = {(z,y) in B : X_y is non-empty}
max possible front coverage <= |U_A|/|A|
max possible side  coverage <= |U_B|/|B|
```

This has to be evaluated before any 3-view/top work. If a row exists in only one image, no exact shared 3D point can represent that row without projection-only/fallback points.

2. Top synthesis was still a single greedy construction. That did not separate two different choices:
   - `C = target ∩ S`: maximize target fidelity while staying supportable.
   - `C = greedy row cover`: cover front/side rows while biasing toward target.

These are not equivalent. A valid top support can preserve top precision but lose front/side, or preserve front/side upper bounds but become less recognizable.

3. The top-slack discussion was not operational enough. Dilation of the target top can only help if new pixels enter the coactivity envelope `S`; if `S` is already the limiting shape, increasing target dilation just adds off-target pixels and lowers precision.

4. Angular morph still lacked a binary decision test. The missing necessary condition for color-only is support equality up to tolerance:

```text
B_target subset dilate(B_canonical, eps)
and
B_canonical subset dilate(B_target, eps)
```

If this fails at a physical tolerance, color-only cannot create/delete silhouette support without opacity/background cheating. Then the case is geometry-needed or should be rejected.

5. The previous experiments still use real images but not browser render captures. That remains a limitation: PIL resampling and binned graph metrics are proxies, not final visual evidence.

## 2. New concrete progress

I added and ran an iteration-4 throwaway probe. It adds:

1. 2-view row-support upper-bound certificate.
2. Top-support trade-off sweep:
   - `target_dilation_intersection`: `C = dilate(C_target,r) ∩ S`
   - `cover_greedy_biased_to_dilated_target`: row-covering top support biased toward target/dilated target
3. Angular morph support-difference test on `goose`, using synthetic shifts by 2/4/8/16 px.

## 3. 2-view row-support upper-bound results

### goose + nubzuki

```text
front_pixels_in_matched_rows_ratio = 0.840105
side_pixels_in_matched_rows_ratio  = 0.798917
front_only_row_count = 24
side_only_row_count  = 29
matched_row_count    = 120
```

This explains why all generated/self-exact top attempts for goose+nubzuki cap out near front IoU 0.840 and side IoU 0.799. The cap exists before the top image is considered.

### goose + cake

```text
front_pixels_in_matched_rows_ratio = 1.000000
side_pixels_in_matched_rows_ratio  = 0.755777
front_only_row_count = 0
side_only_row_count  = 46
matched_row_count    = 144
```

This explains why goose+cake preserves the front perfectly but cannot preserve all side rows. Cake has many rows where goose has no corresponding row support.

Updated rule: a future harness should fail fast or warn before 3-view if these upper bounds are below the desired canonical IoU threshold. This is stronger than only measuring final projection IoU.

## 4. Top trade-off sweep result

The trade-off sweep did not rescue arbitrary phoenix/kumdori top views.

Best target-only recognizability under exact support is still limited by `target_inside_S_ratio`:

```text
goose+nubzuki+phoenix: target_inside_S_ratio = 0.128686
goose+nubzuki+kumdori: target_inside_S_ratio = 0.151123
goose+cake+phoenix:    target_inside_S_ratio = 0.168901
goose+cake+kumdori:    target_inside_S_ratio = 0.196891
```

Using `C = target ∩ S` gives precision 1.0 and recall equal to those ratios, but it cannot exceed them. For the best case, goose+cake+kumdori:

```text
C=target∩S:
  top_vs_original_target_iou = 0.196891
  top_precision = 1.000000
  top_recall    = 0.196891
  front_iou     = 1.000000
  side_iou      = 0.755777
  row_edge_count_p95 = 160
```

The greedy row-cover variant covers rows with fewer top pixels but looks even less like the top target:

```text
goose+cake+kumdori greedy:
  top_vs_original_target_iou = 0.150259
  top_precision = 1.000000
  top_recall    = 0.150259
  front_iou     = 1.000000
  side_iou      = 0.755777
```

Target dilation did not improve recall against the original target; it mostly adds supportable off-target pixels and reduces precision for phoenix. This means the limiting factor is not merely a small alignment/slack radius. The coactivity envelope `S` is too small/misaligned relative to independent phoenix/kumdori assets.

Updated mathematical ladder:

```text
0. 2-view row-support upper bound:
   |U_A|/|A|, |U_B|/|B|
1. Coactivity envelope:
   S = union_y X_y × Z_y
   target_inside_S_ratio = |C_target ∩ S| / |C_target|
2. Top support choice:
   C_target∩S for max precision/recall under exact support
   or row-cover C for front/side preservation
3. Visual hull certificate:
   H = A ∧ B ∧ C, report pi(H)
4. Density/reveal certificate:
   |H|, row_edge_count p50/p95/max
5. Recognizability:
   IoU/precision/recall/components against intended top image
```

## 5. Angular morph decision test

Synthetic goose support shifts:

```text
same support color-only: pass at eps=0
2px shift:  raw_iou=0.913158, first tolerance covering both supports = 2px
4px shift:  raw_iou=0.834060, first tolerance covering both supports = 4px
8px shift:  raw_iou=0.694206, first tolerance covering both supports = 8px
16px shift: raw_iou=0.475172, no pass up to eps=8px
```

Interpretation:
- If the intended angular change is same support/color-only, directional color basis is valid.
- If the silhouette moves by 2 px, bounded micro-displacement may be physically plausible if the project accepts `eps≈2`.
- If it moves by 4 px, it is borderline and must be treated as research-only with visible proof.
- If it needs 8 px or more, it is geometry-needed and should not be sold as color/material-only.
- If it needs 16 px, it fails even an 8 px tolerance and should be rejected/deferred unless the product explicitly allows view-dependent geometry.

This converts the vague “팔 움직임이면 geometry-needed일 수 있다” into a gate:

```text
supportShiftEps = smallest eps such that
  target_support subset dilate(canonical_support, eps)
  and canonical_support subset dilate(target_support, eps)

if supportShiftEps == 0: color-only feasible
elif supportShiftEps <= 2: micro-displacement candidate
elif supportShiftEps <= 4: borderline research-only
else: geometry-needed / defer
```

## 6. Updated implementation spike order

1. Add browser-equivalent extraction/render harness before production code changes.
2. Row materialization spike remains `quantile_max` first.
3. Directional color spike remains valid, but must include rendered mid-angle contact sheet and pop metrics.
4. Add 2-view row-support upper-bound QA before any 3-view/top attempt.
5. Keep arbitrary phoenix/kumdori top out of production. Current numbers are far below recognizability and exact side/front thresholds.
6. For angular morph, implement the support-difference classifier first; only then consider micro-displacement experiments.

## 7. Open questions for next iteration

1. Browser/Node canvas parity: reproduce iteration-3/4 extraction with JS canvas, not PIL.
2. Visual evidence: contact sheets for current shuffle vs quantile rows and directional color mid-angles.
3. Top recognizability metric needs connected-component/skeleton metrics, not only IoU/recall.
4. Investigate co-designed 3-view assets: if front/right/top are designed jointly, can `target_inside_S_ratio` exceed 0.8 while staying recognizable?
5. If row support mismatch is caused by active-bound normalization, test whether controlled vertical alignment/cropping improves the 2-view upper bound without cheating.
6. For morph, test localized limb shifts instead of whole-object shifts; whole-object shift is a strict synthetic bound, not a real animation case.

## 8. Iteration 4 bottom line

- Strengthened: before any 3-view solver, the pipeline needs a 2-view row-support upper-bound certificate. It explains the observed IoU ceilings.
- Strengthened: arbitrary phoenix/kumdori top views remain infeasible/low-recognition even with target dilation and greedy support trade-offs.
- Strengthened: angular morph now has a concrete support-difference gate separating color-only, micro-displacement candidate, borderline research, and geometry-needed cases.
- Still uncertain: browser render parity and visual contact sheets are not yet done.
