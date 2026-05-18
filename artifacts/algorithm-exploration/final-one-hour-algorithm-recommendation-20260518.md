# Final one-hour algorithm recommendation — 2026-05-18

작업 디렉터리: `C:\00_Codes\illusion-3d`
브랜치 기대값/확인값: `algorithm-exploration-20260518`
Production 파일 수정 여부: 수정하지 않음. 본 최종 종합은 `artifacts/algorithm-exploration/` 아래 연구 산출물로만 저장한다.

읽은/종합한 산출물:
- `deep-algorithm-proposal-20260518.md`
- `verification-plan-20260518.md`
- `artifacts/.hermes/algorithm_exploration_probe_20260518.json`
- `iterative-deepening-log-20260518.md`
- iteration 산출물 22개: iteration 1~11의 md/json 파일 전체

반복 횟수: 총 11회

---

## 1. 최종 결론

1시간 반복 탐색의 최종 추천은 다음으로 고정한다.

```text
Production 후보 1순위:
  quantile_max row materialization

Production 후보 2순위:
  cosine_s1 directional color basis

Research-only:
  endpoint-zero micro-displacement morph gate

Production 금지/보류:
  arbitrary 3-view top image, projection-only point, fallback point, top-only point
```

핵심 이유는 단순하다.

- `quantile_max`는 현재 `max+reuse`의 장점인 point budget과 matched-row projection coverage를 유지하면서, row 내부 z-order chaos를 거의 제거한다.
- `cosine_s1` directional color는 fixed RGB blend의 endpoint color 훼손을 크게 줄이면서 opacity gate나 texture swap 없이 구현 가능한 가장 안전한 첫 basis다.
- 3-view는 임의 top 이미지를 추가하는 문제가 아니라 `A(x,y), B(z,y), C(x,z)`의 exact feasibility 문제다. 현재 phoenix/kumdori 같은 독립 top 후보는 coactivity envelope 안에 충분히 들어오지 않아 production-worthy가 아니다.
- angular morph는 color-only로 support를 생성/삭제할 수 없으므로, 실제 intermediate target support gate를 통과한 경우에만 endpoint-zero micro-displacement research로 다룬다.

---

## 2. 이전 결론을 어떻게 비판/보강했는가

초기 proposal의 방향은 맞았지만, 반복 과정에서 다음 약점들이 드러났다.

### 2.1 Row OT/transport 결론의 약점

초기에는 “balanced OT / color-aware OT”를 1순위처럼 제안했지만, 실제 renderer에 필요한 것은 fractional transport `T_ij`가 아니라 integer point materialization이다. 반복 탐색 후 결론은 full Sinkhorn/OT가 아니라 deterministic quantile rounding으로 좁혀졌다.

최종 row 수식:

```text
For each matched row y:
  X_y = sorted active front x coordinates
  Z_y = sorted active side z coordinates
  N_y = max(|X_y|, |Z_y|)

  x_k = X_y[floor((k + 0.5) |X_y| / N_y)]
  z_k = Z_y[floor((k + 0.5) |Z_y| / N_y)]
  p_k = (x_k, y, z_k)
```

이 방식의 보장/관찰:

```text
matched-row active front pixels covered: true
matched-row active side pixels covered: true
front/side multiplicity spread <= 1
projectionOnlyPointCount = 0
```

중요한 보강점: modulo max-reuse도 multiplicity fairness 일부는 통과할 수 있다. `quantile_max`의 진짜 차별점은 color가 아니라 monotone row order / reveal stability다.

### 2.2 3-view feasibility 결론의 약점

초기에는 `H = A ∧ B ∧ C`와 `π(H)=A/B/C` 조건을 제시했지만, 반복 과정에서 더 앞단의 failure certificate가 필요하다는 점이 드러났다.

최종 3-view feasibility ladder:

```text
0. 2-view row-support upper bound
   U_A = {(x,y) in A : Z_y != empty}
   U_B = {(z,y) in B : X_y != empty}
   max front coverage <= |U_A| / |A|
   max side  coverage <= |U_B| / |B|

1. Top coactivity envelope
   S = union_y X_y × Z_y
   top exactness requires C_target mostly inside S

2. Row graph coverage
   E_y = {(x,z): x in X_y, z in Z_y, C(x,z)=1}
   every front x in row must have degree > 0
   every side z in row must have degree > 0
   every top pixel must have at least one compatible y

3. Visual hull certificate
   H = {(x,y,z): A(x,y)=1 and B(z,y)=1 and C(x,z)=1}
   exact iff π_xy(H)=A, π_zy(H)=B, π_xz(H)=C

4. Recognizability certificate
   recall(C, C_target), IoU, bbox fill delta, component metrics

5. Density/reveal certificate
   |H|, row edge count p50/p95/max, sampled density histogram
```

따라서 “top image 하나 더 넣기”는 production에서 금지해야 한다. co-designed top asset이 아니라면 `C ⊆ S`와 recognizability를 동시에 만족하기 어렵다.

### 2.3 Directional color 결론의 약점

초기에는 endpoint fit만 보고 sharp lobe도 가능해 보였지만, mid-angle pop이 빠져 있었다. 반복 과정에서 actual paired-color pop metric이 추가되었고, sharp lobe는 reject됐다.

최종 color basis 1순위:

```text
theta in [0°, 90°]
w_F(theta) = cos(theta) / (cos(theta) + sin(theta))
w_R(theta) = sin(theta) / (cos(theta) + sin(theta))
c_i(theta) = w_F(theta)cF_i + w_R(theta)cR_i
```

`cosine_s1`을 선택하는 이유:

```text
endpoint leakage = 0
endpoint RMSE = 0 in point-pair model
actual pair pop gate passes on goose+nubzuki and goose+cake
no opacity-to-zero
no texture swap
no projection-only geometry
```

### 2.4 Angular morph 결론의 약점

초기에는 “support가 바뀌면 geometry-needed”라는 말이 너무 거칠었다. 최종적으로는 color-only, micro-displacement candidate, geometry-needed를 수식 gate로 분리했다.

최종 morph gate:

```text
Input:
  S(theta) = fixed geometry/material로 가능한 support
  T(theta) = desired target support

1. color-only support gate
   create = |T \ S| / |T|
   erase  = |S \ T| / |S|
   if create <= 0.01 and erase <= 0.01:
     color/material-only candidate

2. displacement lower-bound gate
   d95 = max(p95_distance(T\S -> S), p95_distance(S\T -> T))
   changed = |S xor T| / |S union T|
   moved_region = affected source support ratio

3. endpoint-zero basis gate
   b(theta) = sin(2theta) for two-view 0°/90° orbit
   b(0°)=0, b(90°)=0, b(45°)=1
   jump = max ||d|| * |b(theta+5°)-b(theta)|

4. classification
   strong research candidate if d95 <= 2px, changed <= 0.15,
     moved_region <= 0.30, jump <= 0.4px/5°
   borderline research-only if d95 <= 4px, changed <= 0.30,
     moved_region <= 0.35, jump <= 0.8px/5°
   otherwise geometry-needed/defer
```

---

## 3. 반복별 새로 얻은 것

### Iteration 1 — real-image row probe

새로 얻은 것:
- Synthetic-only 결론을 실제 reference image proxy로 보강했다.
- `goose+nubzuki`에서 quantile/local color-aware가 conflict mean/p95를 낮췄다.
- `goose+cake`에서는 color-aware가 보편적 이득이 아님을 확인했다.

주요 근거:

```text
goose+nubzuki current_modulo conflict_mean=0.409435
quantile_max conflict_mean=0.377321
color_aware_local conflict_mean=0.374984

goose+cake current_modulo conflict_mean=0.466686
quantile_max conflict_mean=0.469797  # worse
```

결론 변화:
- full OT/Sinkhorn 직행 금지.
- current baseline → quantile materialization → 필요시 local color-aware 순서로 축소.

### Iteration 2 — real top graph certificate + lobe sweep

새로 얻은 것:
- 실제 `phoenix/kumdori` top 후보가 3-view exact feasibility에서 실패함을 확인했다.
- top support feasibility 조건 `C ⊆ S = ⋃_y X_y×Z_y`를 명확히 했다.
- sharp lobe `s=8/16`은 endpoint는 맞아도 mid-angle pop이 큰 것으로 분류했다.

주요 근거:

```text
goose+nubzuki+phoenix top_iou=0.327256, unsupported_top_ratio=0.672744
goose+cake+kumdori top_iou=0.537625, unsupported_top_ratio=0.462375

normalized_cosine_power s=8 max_5deg_weight_jump=0.302724
normalized_cosine_power s=1 max_5deg_weight_jump=0.080450
```

### Iteration 3 — production-like extraction + compatible top synthesis

새로 얻은 것:
- production 상수에 가까운 extraction으로 row materialization을 다시 검증했다.
- `quantile_max`가 z-jump를 97~98% 줄이는 것을 확인했다.
- exact-compatible top을 target-biased로 만들어도 phoenix/kumdori recognizability가 매우 낮음을 확인했다.

주요 근거:

```text
goose+nubzuki z_jump_mean:
  current=34.464
  quantile=0.946

goose+cake z_jump_mean:
  current=48.692
  quantile=0.966

target_inside_S_ratio:
  goose+nubzuki+phoenix=0.128686
  goose+cake+kumdori=0.196891
```

### Iteration 4 — feasibility ladder + support morph test

새로 얻은 것:
- 2-view row-support upper bound를 공식 gate로 추가했다.
- top dilation이 arbitrary top을 rescue하지 못함을 확인했다.
- support-difference 기반 color-only 판정법을 만들었다.

주요 근거:

```text
goose+nubzuki front upper=0.840105, side upper=0.798917
goose+cake front upper=1.000000, side upper=0.755777
```

### Iteration 5 — top recognizability metrics + row alignment falsification

새로 얻은 것:
- row shift/cropping이 row-support cap을 의미 있게 고치지 못함을 확인했다.
- exact-supported top candidate가 disconnected noise는 아니지만, recall/scale이 낮아 semantic top으로 읽히지 않음을 확인했다.

주요 근거:

```text
goose+nubzuki best row shift = 0

goose+cake best side improvement shift:
  side_upper 0.755777 -> 0.760597
  front_upper 1.000000 -> 0.901704  # unacceptable trade-off

goose+cake+kumdori C=target∩S:
  recall=0.196891
  candidate pixels=228 vs target 1158
  bbox_fill_delta=+0.354858
```

### Iteration 6 — visual contact sheets + actual paired-color pop

새로 얻은 것:
- row-pairing contact sheet와 row-order chaos metrics를 추가했다.
- actual paired colors에서 directional basis pop을 측정했다.
- `cosine_s8` sharp lobe를 명확히 reject했다.

주요 근거:

```text
goose+nubzuki:
  current z_jump_gt25_ratio=0.518373
  quantile z_jump_gt25_ratio=0.000000
  current direction_flip_ratio=0.657731
  quantile direction_flip_ratio=0.000000

goose+cake:
  current z_jump_gt25_ratio=0.679287
  quantile z_jump_gt25_ratio=0.000000

cosine_s1 actual-pair max_5deg_step_mean=0.031507
cosine_s8 actual-pair max_5deg_step_mean=0.118556
```

### Iteration 7 — decision gates

새로 얻은 것:
- `quantile_max` promotion gate를 수치화하고 양쪽 pair에서 PASS를 확인했다.
- directional color 후보 중 `cosine_s1`만 두 pair 모두 통과함을 확인했다.

Row gate:

```text
front_iou_delta_vs_current >= -0.005
side_iou_delta_vs_current >= -0.005
z_jump_gt25_ratio <= 0.01
direction_flip_ratio_mean <= 0.01
projectionOnlyPointCount = 0
```

Directional gate:

```text
endpoint_rmse <= 0.25 * fixed_blend_endpoint_rmse
max_5deg_step_mean <= 0.04
p99_step <= 0.10
max_accel <= 0.01
wrong_lobe_endpoint <= 0.06
```

결과:

```text
quantile_max row gate: PASS on goose+nubzuki and goose+cake
cosine_s1 directional gate: PASS on goose+nubzuki and goose+cake
cosine_s2/softmax_tau035: fail or narrowly miss on goose+cake
cosine_s8/gaussian_sigma05: fail
```

### Iteration 8 — rendered endpoint color proxy + integer certificate

새로 얻은 것:
- point-pair RMSE가 아니라 projection-pixel aggregate endpoint error를 측정했다.
- fixed blend가 projection pixel 단위에서도 endpoint 색을 크게 훼손함을 확인했다.
- `quantile_max` integer materialization certificate를 정리했다.

주요 근거:

```text
goose+nubzuki quantile:
  front_fixed_rendered_rmse=0.480755
  side_fixed_rendered_rmse=0.265185
  directional endpoint rmse≈0

goose+cake quantile:
  front_fixed_rendered_rmse=0.616528
  side_fixed_rendered_rmse=0.326894
  side_directional_endpoint_rmse=0.019066
```

결론 변화:
- `quantile_max`는 color optimizer가 아니라 fair integer materialization + monotone order로 설명해야 한다.
- directional color 우선순위는 더 강해졌다.

### Iteration 9 — color-only support 판정법

새로 얻은 것:
- directional color가 가능한 경우와 geometry가 필요한 경우를 support set 조건으로 분리했다.
- 같은 projection에서 asset support를 바꾸는 것은 color-only로 불가능하다는 필요조건을 실제 reference mask로 확인했다.

주요 근거:

```text
goose right_2px shift:
  create_missing_ratio=0.210054
  erase_ratio=0.210054
  geometry_needed_if_no_opacity_gate=true

goose -> cake:
  missing_ratio=0.843284
  erase_ratio=0.011969
  geometry_needed=true
```

### Iteration 10 — localized morph displacement lower-bound

새로 얻은 것:
- whole-object shift와 localized part shift를 분리했다.
- color-only 실패 후 바로 geometry-needed로 가지 않고 micro-displacement lower-bound gate를 추가했다.

주요 근거:

```text
right_tail_2px:
  create=0.0606, erase=0.0606, symdiff=0.1143
  p95 distance=2px
  class=micro_displacement_candidate_strong

right_tail_4px:
  symdiff=0.1970, p95=3.606px
  class=micro_displacement_candidate_borderline

right_tail_8px:
  symdiff=0.3121, p95=6.479px
  class=geometry_needed_or_defer
```

### Iteration 11 — endpoint-zero micro-displacement gate

새로 얻은 것:
- micro-displacement가 canonical endpoint를 보존하려면 `b(0)=b(90)=0` 조건이 필요함을 수식화했다.
- `b(theta)=sin(2theta)` 기준 per-frame jump를 gate에 추가했다.

주요 근거:

```text
right_tail_right_2px:
  create=0.068657, erase=0.068657, symdiff=0.128492
  nearest p95=2px
  endpoint max_5deg_jump=0.3473px
  class=endpoint_zero_micro_displacement_strong_candidate

right_tail_right_4px:
  symdiff=0.220924
  nearest p95=4px
  endpoint max_5deg_jump=0.6946px
  class=endpoint_zero_micro_displacement_borderline_research_only

right_tail_diag_4_2px:
  create nearest p95=4.1231px
  class=geometry_needed_or_defer
```

---

## 4. 최종 수학적 조건

### 4.1 2-view row materialization 조건

Production 후보는 `quantile_max`다.

```text
N_y = max(|X_y|, |Z_y|)
x_k = Q_X((k+0.5)/N_y)
z_k = Q_Z((k+0.5)/N_y)
p_k = (x_k, y, z_k)
```

Promotion gate:

```text
projectionOnlyPointCount = 0
front_iou_delta_vs_current >= -0.005
side_iou_delta_vs_current >= -0.005
all matched-row active pixels covered
multiplicity spread <= 1
z_jump_gt25_ratio <= 0.01
direction_flip_ratio_mean <= 0.01
color_conflict reported, not required to improve
```

### 4.2 Directional color 조건

Production 후보 basis는 `cosine_s1`이다.

```text
wF = cos(theta)/(cos(theta)+sin(theta))
wR = sin(theta)/(cos(theta)+sin(theta))
c(theta)=wF*cF+wR*cR
```

Promotion gate:

```text
endpoint_rmse <= 25% of fixed blend endpoint RMSE
wrong_lobe_endpoint = 0, or explicitly <= 0.06
max_5deg_step_mean <= 0.04 before visual calibration
p99_step <= 0.10 before visual calibration
max_accel <= 0.01 before visual calibration
alpha-to-zero = false
view-dependent opacity gate = false
texture swap = false
```

### 4.3 3-view exact feasibility 조건

```text
A ⊂ X×Y
B ⊂ Z×Y
C ⊂ X×Z
H = {(x,y,z): A(x,y)=1 and B(z,y)=1 and C(x,z)=1}

Exact iff:
  π_xy(H)=A
  π_zy(H)=B
  π_xz(H)=C
```

하지만 solver 전에 다음 necessary gates를 먼저 통과해야 한다.

```text
2-view row-support upper bound high enough
C_target mostly inside S = union_y X_y×Z_y
row graph has no isolated front/side/top support
recognizability recall/IoU/shape metrics pass
density/reveal budget pass
```

현재 tested arbitrary top assets는 이 조건을 통과하지 못했다.

### 4.4 Angular morph 조건

```text
color-only feasible iff:
  |T\S|/|T| <= 0.01 and |S\T|/|S| <= 0.01
```

micro-displacement는 research-only이며 endpoint-zero 조건이 필요하다.

```text
p_i(theta)=p_i0+d_i*b(theta)
b(canonical_angles)=0
for 2-view front/right: b(theta)=sin(2theta)
```

Classification:

```text
strong research candidate:
  d95 <= 2px
  changed <= 0.15
  moved_region <= 0.30
  jump <= 0.4px per 5°

borderline research-only:
  d95 <= 4px
  changed <= 0.30
  moved_region <= 0.35
  jump <= 0.8px per 5°

otherwise:
  geometry-needed/defer
```

---

## 5. 검증 근거 요약

### Row materialization

```text
goose+nubzuki:
  current front/side IoU = 0.837755 / 0.799430
  quantile front/side IoU = 0.837755 / 0.799430
  z_jump_gt25_ratio: 0.518373 -> 0.000000
  direction_flip_ratio: 0.657731 -> 0.000000

goose+cake:
  current front/side IoU = 1.000000 / 0.755999
  quantile front/side IoU = 1.000000 / 0.755999
  z_jump_gt25_ratio: 0.679287 -> 0.000000
  direction_flip_ratio: 0.667049 -> 0.000000
```

Interpretation:
- projection cost 없이 row-order chaos가 제거된다.
- color conflict는 pair-dependent이므로 acceptance criterion이 아니다.

### Directional color

```text
goose+nubzuki fixed_blend_endpoint_rmse_mean=0.195815
cosine_s1 endpoint_fraction=0.000000
cosine_s1 max_5deg_step_mean=0.031507
cosine_s1 p99_step=0.071634
cosine_s1 accel=0.004310


goose+cake fixed_blend_endpoint_rmse_mean=0.240213
cosine_s1 endpoint_fraction=0.000000
cosine_s1 max_5deg_step_mean=0.038650
cosine_s1 p99_step=0.068622
cosine_s1 accel=0.005287
```

Interpretation:
- `cosine_s1`만 두 tested pair에서 provisional gate를 모두 통과했다.
- `cosine_s8`은 endpoint exact라도 pop 때문에 reject한다.

### 3-view

```text
target_inside_S_ratio:
  goose+nubzuki+phoenix = 0.128686
  goose+nubzuki+kumdori = 0.151123
  goose+cake+phoenix    = 0.168901
  goose+cake+kumdori    = 0.196891

best exact-support top recall ≈ 8–20%
```

Interpretation:
- arbitrary phoenix/kumdori top은 현재 front/right pair와 물리적으로 잘 맞지 않는다.
- exact supportability를 만족해도 recognizability가 낮아 production top으로 부적합하다.

### Morph

```text
right-tail 2px motion:
  color-only: fail
  endpoint-zero micro-displacement: strong research candidate

right-tail 4px motion:
  color-only: fail
  endpoint-zero micro-displacement: borderline research-only

8px급 또는 asset-swap급 support change:
  geometry-needed/defer
```

Interpretation:
- morph는 production feature가 아니라 actual target gate 후 research spike다.

---

## 6. 최종 구현 spike 우선순위

### 1순위 — Browser/Node canvas parity harness

Production 변경 전에 JS/canvas 또는 browser capture로 proxy 결과를 재현한다.

필수 출력:

```text
current_shuffled_max_reuse vs quantile_max
front_iou, side_iou
z_jump_gt25_ratio
z_jump_gt50_ratio
direction_flip_ratio_mean
matched-row coverage
multiplicity spread
projectionOnlyPointCount=0
row/reveal contact sheet
```

Acceptance:

```text
quantile_max가 iteration 7 row gate를 통과해야 함
actual rendered reveal에서 barcode/reveal chaos 감소가 보여야 함
```

### 2순위 — `quantile_max` production candidate

JS parity가 맞으면 production에 최소 변경으로 이식한다.

주의:
- `src/main.ts` 변경은 별도 implementation 단계에서만 한다.
- projection-only/top/fallback point는 추가하지 않는다.
- full OT/Sinkhorn은 지금 구현하지 않는다.

### 3순위 — `cosine_s1` directional color shader spike

먼저 throwaway/browser harness에서 fixed blend와 비교한다.

필수 출력:

```text
front/right endpoint rendered color RMSE
mid-angle contact sheet every 5° or 10°
max_5deg_step_mean / p99 / accel
wrong_lobe_endpoint
alpha-to-zero=false
```

Acceptance:

```text
endpoint RMSE <= fixed blend의 25%
max_5deg_step_mean <= provisional 0.04 또는 contact-sheet에서 명확히 acceptable
no opacity gate
no texture swap
```

### 4순위 — Angular support classifier

Morph 요구가 있을 때만 actual intermediate target mask에 적용한다.

순서:

```text
1. color-only support gate
2. displacement lower-bound gate
3. endpoint-zero basis jump gate
4. strong/borderline/geometry-needed classification
5. strong일 때만 throwaway micro-displacement renderer
```

### 5순위 — 3-view research protocol

3-view는 arbitrary asset adaptation이 아니라 co-designed asset protocol이 생길 때만 재개한다.

필수 gate:

```text
row-support upper bound high enough
C_target_inside_S_ratio preferably high, provisional >= 0.70 recall target
C ⊆ S or explicitly soft/research-labeled
visual hull π(H) metrics pass
recognizability metrics pass
|H|/density/reveal budget pass
```

---

## 7. 남은 불확실성

1. Browser/WebGL parity가 아직 최종 확인되지 않았다. 현재 많은 수치는 production-like PIL/canvas proxy다.
2. 실제 WebGL splat/glow/additive blending에서 directional endpoint가 얼마나 유지되는지 contact sheet가 필요하다.
3. `max_5deg_step_mean <= 0.04`, `p99 <= 0.10` 같은 color pop threshold는 provisional이다. 실제 screenshot으로 보정해야 한다.
4. Morph는 실제 intermediate target이 없다. Goose right-tail proxy는 gate를 강화하기 위한 synthetic case일 뿐이다.
5. Micro-displacement는 2D support lower-bound만 확인했다. 실제 3D coupling에서 right/reveal projection이 깨질 수 있다.
6. 3-view는 co-designed asset 없이는 positive path가 없다. 임의 phoenix/kumdori top은 반복적으로 실패했다.

---

## 8. 최종 권고

가장 안전한 다음 구현 방향은 다음이다.

```text
1. Browser/Node parity harness 작성
2. quantile_max row materialization 검증 및 이식
3. cosine_s1 directional color shader 검증 및 이식
4. morph는 actual target gate 통과 시 research-only
5. 3-view는 co-designed assets와 feasibility/recognizability gates 없이는 production 금지
```

절대 하지 말아야 할 것:

```text
- projection-only/top/fallback point 추가
- arbitrary third image를 top view로 끼워 넣기
- fixed blend 색 문제를 opacity gate나 texture swap으로 숨기기
- color basis로 support/silhouette morph까지 해결한다고 주장하기
- full OT/Sinkhorn을 quantile_max 검증 전에 구현하기
```

최종 한 줄 결론:

`quantile_max`로 shared point cloud의 row/reveal stability를 먼저 고치고, `cosine_s1` directional color로 fixed blend의 endpoint color 훼손을 줄인다. 3-view와 morph는 수학적 feasibility gate를 통과한 경우에만 research로 진행하며, production에는 projection-only/top/fallback 계열 shortcut을 절대 넣지 않는다.
