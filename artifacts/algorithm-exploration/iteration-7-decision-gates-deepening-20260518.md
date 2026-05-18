# Iteration 7 — decision gates for row materialization and directional color

Scope guard:
- Branch checked by tool: `algorithm-exploration-20260518`.
- Production files were not modified.
- New throwaway script: `artifacts/.hermes/iteration7_decision_probe_20260518.py`.
- New result JSON: `artifacts/algorithm-exploration/iteration-7-decision-probe-20260518.json`.
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
