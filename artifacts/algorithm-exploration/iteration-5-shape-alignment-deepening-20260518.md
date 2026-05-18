# Iteration 5 — top recognizability metrics + row-alignment falsification

Scope guard:
- Branch: `algorithm-exploration-20260518` was checked before this iteration.
- Production files were not modified.
- New throwaway script: `artifacts/.hermes/iteration5_shape_alignment_probe_20260518.py`.
- New result JSON: `artifacts/algorithm-exploration/iteration-5-shape-alignment-probe-20260518.json`.
- Prior artifacts read: base proposal, verification plan, original probe JSON, and iterative log through iteration 4.

## A. Critique of prior conclusions

Iteration 4 was useful but still incomplete in three ways.

1. Top recognizability was judged mostly by IoU/precision/recall. That is not enough. A candidate can be one connected blob with high precision and still be a small dense patch rather than a recognizable phoenix/kumdori. Missing metrics:

```text
component_count(C)
largest_component_ratio(C)
isolated_pixel_ratio(C)
mean_8neighbor_count(C)
bbox_fill_ratio(C)
shape_delta(C, C_target)
```

2. The “active-bound normalization may cause row mismatch” uncertainty had not been tested. If a simple integer row shift greatly improved `front_pixels_in_matched_rows_ratio` or `side_pixels_in_matched_rows_ratio`, then the 2-view row-support cap would be partly an alignment artifact rather than an asset-incompatibility fact.

3. The previous top-synthesis critique did not state a necessary recognizability lower bound. Exact feasibility alone is too weak. For a top candidate to be production-worthy, it should satisfy both:

```text
C ⊆ S = union_y X_y × Z_y          # physical supportability
recall(C, C_target) high enough     # intended top image remains legible
shape(C) close to shape(C_target)   # not just a clipped dense patch
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

For goose+cake, shifting can raise side upper bound only from `0.755777` to `0.760597`, while damaging front from `1.0` to `0.901704`. Therefore alignment/cropping cannot rescue the side mismatch in any useful way.

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

### Best available case: goose + cake + kumdori

`C = target ∩ S`:

```text
IoU/recall vs target = 0.196891
precision = 1.000000
candidate pixels = 228 vs target 1158
component_count = 1
mean_8neighbor_count = 7.228070 vs target 7.322971
bbox_fill_ratio = 0.957983 vs target 0.603125
bbox_fill_ratio_delta = +0.354858
```

Interpretation: it is not a scattered noise cloud; it is one connected dense support patch. But it is only ~20% of the intended shape and has an overly dense/fill-like bounding box. That means it will read as a clipped blob/stencil, not as kumdori.

Greedy row-cover candidate:

```text
IoU/recall vs target = 0.150259
precision = 1.000000
candidate pixels = 174 vs target 1158
mean_8neighbor_count = 7.034483
bbox_fill_ratio_delta = +0.127967
```

This preserves row-covering constraints but is even less recognizable.

### Worst/typical cases

```text
goose+nubzuki+phoenix:
  target_inside_S_ratio = 0.128686
  greedy recall = 0.084004
  greedy bbox_fill_ratio_delta = -0.223462

goose+nubzuki+kumdori:
  target_inside_S_ratio = 0.151123
  greedy recall = 0.107945

goose+cake+phoenix:
  target_inside_S_ratio = 0.168901
  greedy recall = 0.120643
```

All are below any plausible recognizability threshold.

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

A concrete provisional top recognizability threshold for future experiments:

```text
recall(C, C_target) >= 0.70
IoU(C, C_target) >= 0.50
abs(bbox_fill_ratio_delta) <= 0.15
mean_8neighbor_count_delta >= -1.0
largest_component_ratio >= 0.80
```

Current phoenix/kumdori candidates fail primarily on recall/IoU, even when shape connectivity is not terrible.

## F. Updated implementation spike order

1. Keep production unchanged.
2. Browser-equivalent extraction/render harness remains the next verification blocker.
3. Row materialization candidate remains `quantile_max`; row-shift/cropping is not a useful rescue path for these assets.
4. Directional color remains the strongest near-term feature because fixed blend endpoint error is already shown large and no opacity/projection-only points are needed.
5. 3-view must stay research-only unless assets are co-designed so that `C_target ∩ S` recall is high. Arbitrary phoenix/kumdori top views remain rejected.
6. Future top generation should optimize under `C ⊆ S` but target recognizability must be measured by recall + shape metrics, not exactness alone.

## G. Open questions for next iteration

1. Build a browser/Node canvas parity harness and compare PIL proxy metrics against actual JS/canvas extraction.
2. Generate visual contact sheets for `current_shuffled_max_reuse` vs `quantile_max` to confirm the z-jump improvement is visible.
3. Render directional color basis at mid-angles and compute visible pop/ΔE on actual paired colors.
4. Try co-designed top supports by constructing `C_target` from `S` first, then assessing whether humans can recognize it as a deliberate image.
5. Replace the simple shape metrics with skeleton/contour metrics if a library is allowed, because current `branchpoint_count` on filled shapes is only a rough density proxy.
6. Test localized limb morph support changes, not only whole-object shifts.

## H. Iteration 5 bottom line

- Strengthened: the row-support cap is not fixed by simple vertical alignment; shift 0 is already best for harmonic upper bound on both tested pairs.
- Strengthened: exact-supported top candidates fail recognizability mainly because recall is only ~8–20%, not because they are random disconnected noise.
- Refined: 3-view QA must include recognizability shape metrics after `C ⊆ S`; exact feasibility alone can produce a small connected but semantically useless blob.
- Still uncertain: browser parity and rendered visual evidence remain the two main verification gaps.
