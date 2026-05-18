# Iteration 11 — endpoint-zero micro-displacement gate deepening

작업 디렉터리: `C:\00_Codes\illusion-3d`
브랜치 확인: `algorithm-exploration-20260518`
Production 파일 수정 여부: 수정하지 않음. 새 throwaway script와 연구 산출물만 추가했다.

추가/실행 파일:

```text
artifacts/.hermes/iteration11_endpoint_zero_displacement_probe_20260518.py
artifacts/algorithm-exploration/iteration-11-endpoint-zero-displacement-probe-20260518.json
```

## A. 이전 결론 비판

Iteration 10의 결론은 `color-only`, `micro-displacement candidate`, `geometry-needed/defer`를 분리했다는 점에서 유효하지만 아직 얕은 부분이 있었다.

1. `distance p95 <= 2/4px`는 lower-bound일 뿐, 실제로 카메라 각도 0°와 90° canonical endpoint를 보존하는 displacement 함수가 가능한지 확인하지 않았다.
2. `micro-displacement candidate`라는 말이 실제 구현 가능한 형태인지 불명확했다. 즉 `p_i(theta)=p_i0+delta_i*b(theta)`에서 `b(0)=b(90)=0` 같은 endpoint-zero 조건이 빠져 있었다.
3. displacement smoothness metric이 없었다. 같은 4px 변화라도 5° frame step에서 0.7px씩 튀는지, 2px 변화처럼 0.35px 정도인지 구분해야 한다.
4. localized shift를 “rightmost 25% proxy”로만 봤고, 그 region size가 physical plausibility에 미치는 영향을 gate에 넣지 않았다. 전체 support의 25~30%가 움직이면 2px라도 이미 꽤 큰 morph다.
5. 여전히 실제 intermediate product target은 없다. 이번 iteration도 실제 goose reference mask 기반의 synthetic localized target이다. 따라서 제품 pass/fail이 아니라 spike gate 강화로 해석해야 한다.

## B. 새로 만든 구체적 진전

Endpoint-zero micro-displacement의 최소 수식을 gate에 추가했다.

```text
p_i(theta) = p_i0 + d_i * b(theta)
b(theta) = sin(2theta), theta in [0°, 90°]
b(0°)=0, b(90°)=0, b(45°)=1
```

이 수식은 canonical front/right endpoint를 보존하면서 중간각에서만 displacement가 최대가 되는 가장 단순한 research-only morph basis다. 이것은 production 추천이 아니라, micro-displacement를 검토할 때 최소한 통과해야 하는 조건이다.

새 probe는 실제 `artifacts/reference-image/goose.png`를 160×120 proxy mask로 읽고, right-tail region을 x 75% quantile 이상 support로 잡았다. 그 region을 여러 방향/크기로 이동시킨 뒤 다음을 측정했다.

```text
create_ratio_vs_target = |T \ S| / |T|
erase_ratio_vs_base    = |S \ T| / |S|
symdiff_ratio_vs_union = |S xor T| / |S union T|
create/erase nearest-support p95/max
endpoint-zero basis max_5deg_displacement_jump
classification
```

분류는 다음처럼 보강했다.

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

## C. 실행 결과 요약

Base/proxy:

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

1. 1~2px localized tail motion은 pure color-only가 아니다. create/erase가 1%보다 훨씬 크다.
2. 하지만 endpoint-zero `sin(2theta)` basis를 쓰면 2px motion의 5° step jump가 0.3473px라서 temporal pop 측면에서는 strong research candidate로 볼 수 있다.
3. 4px horizontal/down motion은 p95와 jump가 아직 bound 안에 있지만 IoU가 0.78~0.81 수준이고 changed_ratio가 19~22%라서 production이 아니라 borderline research-only다.
4. diagonal motion은 같은 nominal 2px+2px라도 vector magnitude와 p95가 커져 borderline으로 내려간다. 4px+2px는 p95가 4px를 넘어 geometry-needed/defer다.
5. moved region 자체가 base의 26.8%라서 “작은 part”라고 부르기엔 크다. 실제 limb mask가 이보다 작으면 gate가 완화될 수 있지만, whole object/large part morph는 계속 위험하다.

## D. 업데이트된 수학적 판정법

Angular morph gate를 다음 순서로 갱신한다.

```text
Input:
  S(theta) = fixed geometry/material로 가능한 support
  T(theta) = desired intermediate target support

1. color-only support gate
  if |T\S|/|T| <= 0.01 and |S\T|/|S| <= 0.01:
    color/material-only candidate

2. support displacement lower-bound
  d95 = max(p95_distance(T\S -> S), p95_distance(S\T -> T))
  changed = |S xor T| / |S union T|
  moved_region = estimated affected source support ratio

3. endpoint-zero basis gate
  choose b(theta) with b(canonical_angles)=0
  for 2-view front/right orbit, first probe b(theta)=sin(2theta)
  jump = max over sampled theta of ||d|| * |b(theta+step)-b(theta)|

4. classification
  strong research candidate if d95 <= 2px, changed <= 0.15, moved_region <= 0.30, jump <= 0.4px/5deg
  borderline research-only if d95 <= 4px, changed <= 0.30, moved_region <= 0.35, jump <= 0.8px/5deg
  otherwise geometry-needed/defer
```

중요: 이것도 충분조건은 아니다. 실제 renderer에서 point size/glow/occlusion 때문에 canonical endpoint가 유지되는지, 중간각 silhouette가 target에 가까워지는지, right projection이나 reveal이 깨지지 않는지를 별도 확인해야 한다.

## E. 구현 spike 순서에 미치는 변화

기존 큰 추천은 유지하되, morph spike의 조건이 더 구체화됐다.

1. Near-term production 후보는 여전히 `quantile_max row materialization` + `cosine_s1 directional color`다.
2. Morph는 production 후보가 아니라 research-only spike다.
3. Morph spike를 한다면 무작정 displacement shader부터 만들지 말고, 먼저 actual intermediate target mask에 위 gate를 적용한다.
4. Gate가 strong이면 endpoint-zero basis로 throwaway renderer를 만든다.
5. Gate가 borderline이면 contact sheet와 canonical endpoint damage를 본 뒤 보류/폐기한다.
6. Gate가 geometry-needed면 micro-displacement로 포장하지 말고 geometry/asset redesign 문제로 분류한다.

## F. 남은 불확실성 / 다음 iteration open questions

1. 실제 intermediate target mask가 필요하다. 지금은 goose right-tail proxy라서 제품 요구의 팔/외곽선 변화와 다를 수 있다.
2. `sin(2theta)`는 2-view 0°/90° orbit 전용의 단순 basis다. 3-view나 45° overhead reveal에서는 canonical-zero 조건을 다점 보간 basis로 다시 설계해야 한다.
3. Probe는 2D support만 본다. 실제 3D point가 front screen x로 움직이면 right/reveal에서 어떻게 보이는지 projection coupling을 재야 한다.
4. Moved region ratio 26.8%가 너무 클 수 있다. 다음에는 semantic part mask나 connected component 기반 localized region을 써야 한다.
5. Browser/WebGL splat contact sheet가 아직 없다. point size/glow가 1~2px displacement를 숨기는지 또는 더 튀게 만드는지 확인해야 한다.

## G. Iteration 11 bottom line

- 이번 iteration의 새 진전은 micro-displacement를 “가능할 수도 있음”에서 `endpoint-zero basis + per-frame jump + changed support ratio`를 포함한 gate로 구체화한 것이다.
- 실제 goose mask proxy에서 right-tail 2px 이동은 color-only는 아니지만 endpoint-zero micro-displacement strong research candidate다.
- 4px 이동은 borderline research-only, diagonal 4px+2px는 geometry-needed/defer다.
- 최종 추천은 변하지 않는다. production으로는 row materialization과 directional color를 먼저 검증하고, morph는 실제 intermediate target이 gate를 통과할 때만 throwaway로 진행한다.
