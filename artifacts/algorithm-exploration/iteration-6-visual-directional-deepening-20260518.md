# Iteration 6 — visual contact sheets + actual paired-color pop metrics

Scope guard:
- Branch expected/checked in this run: `algorithm-exploration-20260518`.
- Production files were not modified.
- New throwaway script: `artifacts/.hermes/iteration6_visual_and_directional_probe_20260518.py`.
- New result JSON: `artifacts/algorithm-exploration/iteration-6-visual-directional-probe-20260518.json`.
- New visual evidence:
  - `artifacts/algorithm-exploration/iteration-6-row-pairing-contact-sheet-20260518.png`
  - `artifacts/algorithm-exploration/iteration-6-directional-color-contact-sheet-20260518.png`
- Required prior outputs were read again: base proposal, verification plan, original probe JSON, and the iterative log through iteration 5.

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
