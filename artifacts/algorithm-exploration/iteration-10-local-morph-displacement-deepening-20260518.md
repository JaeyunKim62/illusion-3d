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
