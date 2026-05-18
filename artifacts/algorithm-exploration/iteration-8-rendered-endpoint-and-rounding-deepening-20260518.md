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
