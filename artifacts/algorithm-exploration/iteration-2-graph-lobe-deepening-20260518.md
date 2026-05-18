# Iteration 2 — real top-candidate graph certificate + directional lobe regularizer

Scope guard:
- Branch expected/checked earlier in this iteration: `algorithm-exploration-20260518`.
- Production files were not modified. New files are under `artifacts/.hermes/` and `artifacts/algorithm-exploration/` only.
- Inputs read before this iteration: `deep-algorithm-proposal-20260518.md`, `verification-plan-20260518.md`, `algorithm_exploration_probe_20260518.json`, and `iterative-deepening-log-20260518.md`.

Iteration-specific files:
- `artifacts/.hermes/iteration2_graph_and_lobe_probe_20260518.py`
- `artifacts/algorithm-exploration/iteration-2-graph-and-lobe-probe-20260518.json`
- `artifacts/algorithm-exploration/iteration-2-graph-lobe-deepening-20260518.md`

## 1. Critique of prior outputs

The previous conclusion was useful but still shallow in four places.

### 1.1 3-view exact feasibility was still too global

The previous report correctly stated:

```text
H={(x,y,z): A(x,y)=1 ∧ B(z,y)=1 ∧ C(x,z)=1}
exact feasible iff πxy(H)=A, πzy(H)=B, πxz(H)=C
```

But it did not separate the three distinct failure modes enough:

```text
front/right row support failure:
  isolatedFront(x,y) = [x∈X_y and no z∈Z_y with C(x,z)=1]
  isolatedSide(z,y)  = [z∈Z_y and no x∈X_y with C(x,z)=1]

top support failure:
  unsupportedTop(x,z) = [C(x,z)=1 and no y with x∈X_y and z∈Z_y]

density/reveal failure:
  H may project exactly but have too many edges/voxels per row, causing blocky reveal
```

The old report had the right theorem but not enough certificate fields to diagnose which of these is killing a real top candidate.

### 1.2 Synthetic top probe was weak

Iteration 1 already noted this, but the weakness is stronger: the synthetic diagonal/cutout top does not test actual reference-image supports. In a real top candidate, failure may come less from row graph degree and more from `C` pixels whose `(x,z)` pairs are never co-active in any front/right row. That cannot be inferred from the synthetic probe.

### 1.3 Row OT recommendation still risks overclaiming

Iteration 1 weakened the OT claim: `quantile_max` helped goose+nubzuki but not goose+cake. Therefore the next recommendation should not say “OT is the algorithm”; it should say:

```text
Use current max+reuse as the coverage baseline.
Spike monotone/quantile materialization as a low-risk replacement.
Only add color-aware local/OT if real-pair metrics show repeatable conflict reduction without coverage loss.
```

### 1.4 Directional color needs a basis selection rule, not just a basis list

The old proposal listed lobes/SH/MLP. Iteration 1 added pop metrics, but it still did not answer which family should be tried first. The missing condition is an endpoint-leakage vs mid-angle-pop trade-off:

```text
endpointLeak = wrong lobe weight at θ=0°,90°
pathError    = RMSE(weight_right(θ), desired_mid_angle_weight(θ))
pop          = max_θ |w(θ+Δ)-w(θ)|
accel        = max_θ |w(θ+Δ)-2w(θ)+w(θ-Δ)|
```

A useful basis is not simply the one with zero endpoint error; it must also avoid a sharp 45° switch.

## 2. New concrete progress

I added a throwaway probe that does two things:

1. Runs real reference-image 3-view graph certificates for:
   - front: `goose.png`
   - side: `nubzuki.png`, `cake.png`
   - top: `phoenix.png`, `kumdori.png`
2. Sweeps directional lobe basis families and reports endpoint leakage, linear mid-angle path error, max 5° jump, and acceleration.

This remains a proxy: it resizes/normalizes alpha masks and does not use the production renderer. However, unlike the first synthetic 3-view probe, it uses actual top candidate images.

## 3. Results: real top-candidate 3-view graph certificates

All tested real top candidates fail exact 3-view feasibility at the proxy resolution `96×80×96`.

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

Important interpretation:

- For `goose+nubzuki`, top candidates break both front/side and top badly. The top mask is not the only issue; same-y coactivity between goose and nubzuki is too narrow after normalization.
- For `goose+cake`, front is less damaged (`0.925390`) because cake has much larger row support, but side and top are still far below acceptance.
- `unsupported_top_ratio` is very high (`46%–67%`). This means many top pixels are not realizable by any row where front has that `x` and side has that `z`. This is a stronger failure certificate than IoU alone.
- Row edge density can be high while exact feasibility still fails. Example: `goose+cake+kumdori` has `row_edge_density_mean=0.993705`, yet `top_iou=0.537625`. High edge density within active rows does not help top pixels whose `(x,z)` pairs are never co-active in any row.

Therefore the 3-view recommendation becomes stricter:

```text
Do not try to use phoenix/kumdori as arbitrary third top images with production points.
First generate or select a top image from the front/right coactivity support S={(x,z): ∃y x∈X_y ∧ z∈Z_y}.
Then test whether the chosen top C satisfies C ⊆ S and whether C provides enough row edges to preserve A/B.
```

More formal candidate-top condition:

```text
S = ⋃_y X_y × Z_y
Top support feasibility requires C ⊆ S.
Front preservation requires ∀(x,y)∈A, C_x ∩ Z_y ≠ ∅.
Side preservation requires ∀(z,y)∈B, C^z ∩ X_y ≠ ∅.
```

This is a stronger design rule than the earlier “run visual hull QA” statement: top image selection itself should be constrained by `S` before any point generation.

## 4. Results: directional lobe sweep

The sweep compared three basis families against a simple desired linear angle blend. Endpoint colors are assumed to differ by unit distance, so weight error is a proxy for worst-case color error.

Selected results:

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

The earlier `s=8` lobe looked attractive because endpoint leakage is zero, but the new sweep shows why it pops: max 5° weight jump is `0.302724`, and acceleration is `0.160076`. At `s=16`, the switch is worse (`0.443043`).

New basis recommendation:

```text
For first directional-color spike, do not use sharp s=8/s=16 lobes as the default.
Start with normalized_cosine_power s=1 or softmax_cosine temperature≈0.35.
If canonical color separation needs stronger endpoints, test angular_gaussian sigma≈0.50 but only with pop metric gates.
```

A more robust regularized fitting objective should be:

```text
min_β  L_endpoint(0°,90°)
     + λ_path Σθ ||c(θ)-c_target(θ)||²
     + λ_jump maxθ ||c(θ+Δ)-c(θ)||²
     + λ_accel Σθ ||c(θ+Δ)-2c(θ)+c(θ-Δ)||²
     + λ_leak wrongLobeEndpoint
```

This avoids optimizing only the canonical views and discovering a 45° pop later.

## 5. Updated implementation spike order

1. Keep production unchanged.
2. Build a reusable experiment harness under `artifacts/.hermes/` that mirrors `src/main.ts` extraction more closely.
3. Row matching spike:
   - baseline: current max+reuse
   - candidate 1: `quantile_max`
   - candidate 2: local color-aware quantile only if candidate 1 is not enough
   - defer full Sinkhorn until simple materialization fails
4. Directional color spike:
   - basis sweep first, not shader first
   - default basis: `cosine_power s=1` or `softmax_cosine τ≈0.35`
   - reject basis if `max_5deg_weight_jump` or `max_accel` exceeds visible-pop threshold
5. 3-view spike:
   - first compute support envelope `S=⋃_y X_y×Z_y`
   - reject arbitrary top image if `|C\S|/|C|` is high
   - only then run visual hull `H=A∧B∧C`
   - do not add top/projection-only/fallback production points

## 6. Open questions for iteration 3

1. Production-equivalent extraction: mirror `src/main.ts` canvas size, active-bound normalization, shuffle seed, and row count exactly in the throwaway harness.
2. Top-image design: instead of testing arbitrary phoenix/kumdori masks, generate a top candidate constrained to `S` and measure recognizability vs exact feasibility.
3. Density control: if a compatible top is generated, test sparse sampling of `H` while preserving all three projections. This is a set-cover/hitting problem, not just random downsampling.
4. Directional color with actual paired colors: apply the basis sweep to real matched point colors and report endpoint RMSE vs current fixed blend, not only basis-weight proxy.
5. Define visible-pop thresholds empirically using contact sheets or rendered frame sequences: e.g. max 5° weight jump threshold should map to ΔE/RMSE, not remain abstract.
6. Angular morph decision rule still needs executable support-difference test: when target support changes by more than a small dilation of canonical support, classify as geometry-needed.

## 7. Iteration 2 bottom line

- Strengthened: 3-view exact feasibility now has a real-image row-graph/top-support certificate. Phoenix/kumdori as arbitrary top images fail badly in this proxy, mostly due to unsupported top pixels and side/top projection loss.
- Strengthened: top selection should be constrained by `S=⋃_y X_y×Z_y` before any visual-hull point generation.
- Strengthened: directional color now has a concrete basis/regularizer recommendation. Sharp lobes are risky because they create mid-angle pop even with perfect canonical endpoints.
- Weakened: the earlier “directional lobe s=8 works at endpoints” conclusion is insufficient and should not guide implementation.
- Still uncertain: all image probes are proxy extraction, not exact production renderer output. Iteration 3 should close that gap before recommending code changes.
