# Iteration 9 — color-only support 판정법 + low-pop directional basis 보강

Scope guard:
- Branch checked: `algorithm-exploration-20260518`.
- Production 파일은 수정하지 않았다.
- 새 throwaway script: `artifacts/.hermes/iteration9_support_and_basis_probe_20260518.py`.
- 새 result JSON: `artifacts/algorithm-exploration/iteration-9-support-and-basis-probe-20260518.json`.
- 이번 iteration에서 다시 확인한 기존 산출물: base proposal, verification plan, original probe JSON, iterative log, iteration 8 report.

## A. 이전 결론 비판

Iteration 8까지의 결론은 `quantile_max + cosine_s1 directional color`를 가장 유력한 spike로 압축한 점이 좋다. 하지만 아직 얕은 부분이 남아 있다.

1. Directional color가 endpoint 색을 회복한다는 사실과, angular morph가 색만으로 가능한지는 별개다. 기존 로그는 “silhouette support가 바뀌면 geometry-needed”라고 말했지만, 이를 실제 reference mask에서 판정하는 수식/metric이 부족했다.

2. `cosine_s1` 추천은 pop metric이 낮다는 이유가 있었지만, 후보 basis의 요구조건이 shader promotion rule로 충분히 정리되지 않았다. 특히 endpoint-exact, monotone, max jump, acceleration을 동시에 보는 기준이 필요하다.

3. 실제 이미지를 쓰지 않은 약점은 여전히 남아 있다. Iteration 8은 actual reference color를 썼지만 PIL projection proxy였고, 이번에도 browser/WebGL splat capture가 아니다. 따라서 이번 결과는 “필요조건 판정”이지 최종 visual proof가 아니다.

4. Angular morph 실험 계획은 있었지만, “색-only로 가능한 경우”와 “geometry/micro-displacement가 필요한 경우”를 QA가 자동으로 분류하는 형태가 아니었다. 다음 구현 spike가 scope creep 없이 진행되려면 이 classifier가 먼저 필요하다.

## B. 새로 만든 구체적 진전

새 probe를 작성/실행했다.

```text
python artifacts/.hermes/iteration9_support_and_basis_probe_20260518.py
```

이 probe는 실제 reference image alpha/non-white mask를 `160×120` proxy로 읽고 다음을 계산한다.

1. Color-only/material-only support 판정:

```text
Given fixed projected support Sθ and target support Tθ:
  create_missing = |Tθ \ Sθ|
  erase_needed   = |Sθ \ Tθ|

color-only pass if:
  create_missing / |Tθ| <= 0.01
  erase_needed   / |Sθ| <= 0.01
```

해석:
- `Tθ \ Sθ`는 기존 점 support 밖에 새 foreground를 만들어야 하는 영역이다. 색만으로는 불가능하다.
- `Sθ \ Tθ`는 기존 foreground를 지워야 하는 영역이다. background-colored paint나 alpha-to-zero로 해결하면 opacity gate/cheat 위험이다.
- 따라서 둘 중 하나가 1%를 넘으면 pure directional color가 아니라 micro-displacement 또는 geometry-needed로 분류한다.

2. 실제 reference mask의 shift stress test:
- `goose`, `nubzuki`, `cake`, `phoenix`, `kumdori` mask를 1/2/4/8/12 px 수평 또는 1/2/4/8 px 수직 이동시킨 target과 비교.
- 목적은 “팔/외곽선이 몇 px 움직이면 색-only가 깨지는가”를 수치화하는 것이다.

3. Fixed-view asset support incompatibility:
- `goose -> nubzuki/cake/phoenix/kumdori`를 같은 view support에서 color-only로 바꾸려 할 때 필요한 missing/erase ratio를 계산.
- 이것은 endpoint asset swap을 색만으로 하자는 뜻이 아니라, support mismatch가 얼마나 큰지 보여주는 필요조건 probe다.

4. Directional weight basis 재비교:
- `linear`, `smoothstep`, `smootherstep`, `cosine_s1`, `cosine_s2`, `cosine_s8`를 endpoint leakage, linear path RMSE, max 5° jump, acceleration, monotonicity로 비교.

## C. 실행 결과 요약

### 1. Goose mask shift: 2 px도 color-only로는 이미 실패

```text
goose right_2px:
  create_missing_ratio_vs_target = 0.210054
  erase_ratio_vs_base            = 0.210054
  IoU                            = 0.652819
  geometry_needed_if_no_opacity_gate = true

goose right_4px:
  create_missing_ratio_vs_target = 0.381807
  erase_ratio_vs_base            = 0.381807
  IoU                            = 0.447380

goose right_8px:
  create_missing_ratio_vs_target = 0.562537
  erase_ratio_vs_base            = 0.562537
  IoU                            = 0.279969

goose down_4px:
  create_missing_ratio_vs_target = 0.516457
  erase_ratio_vs_base            = 0.516457
  IoU                            = 0.318863
```

해석:
- 얇은 limb 하나가 아니라 전체 mask shift라서 stress test가 강한 편이지만, 핵심은 분명하다. contour/support가 조금만 이동해도 pure color-only는 빠르게 실패한다.
- “팔이 움직인다”가 실제 silhouette 이동이면 `cosine_s1` shader로 해결할 문제가 아니다. micro-displacement 후보로도 2~4 px bound를 넘는 영역 비율을 따져야 한다.

### 2. Asset support mismatch는 color-only로 불가능

```text
goose -> nubzuki:
  missing_ratio = 0.749360
  erase_ratio   = 0.238181
  IoU           = 0.232427
  geometry_needed = true

goose -> cake:
  missing_ratio = 0.843284
  erase_ratio   = 0.011969
  IoU           = 0.156419
  geometry_needed = true

goose -> phoenix:
  missing_ratio = 0.911604
  erase_ratio   = 0.427887
  IoU           = 0.082914
  geometry_needed = true

goose -> kumdori:
  missing_ratio = 0.855198
  erase_ratio   = 0.000598
  IoU           = 0.144789
  geometry_needed = true
```

해석:
- Directional color는 endpoint color conflict를 해결하는 기술이지, 서로 다른 silhouette support를 같은 camera support에서 만들어내는 기술이 아니다.
- 현재 2-view illusion이 가능한 이유는 front/right가 서로 다른 projection 축을 쓰기 때문이다. 같은 projection support에서 asset을 바꾸려면 새 foreground 생성/삭제가 필요해진다.

### 3. Basis 비교: sharp lobe는 pop 때문에 계속 reject

```text
linear:
  endpoint leakage = 0 / 0
  linear_path_rmse = 0.000000
  max_5deg_jump    = 0.055556
  max_5deg_accel   ≈ 0
  monotone         = true

cosine_s1:
  endpoint leakage = 0 / 0
  linear_path_rmse = 0.031562
  max_5deg_jump    = 0.080450
  max_5deg_accel   = 0.011004
  monotone         = true

smoothstep:
  endpoint leakage = 0 / 0
  linear_path_rmse = 0.067159
  max_5deg_jump    = 0.082990
  max_5deg_accel   = 0.016461
  monotone         = true

smootherstep:
  endpoint leakage = 0 / 0
  linear_path_rmse = 0.101257
  max_5deg_jump    = 0.103313
  max_5deg_accel   = 0.017623
  monotone         = true

cosine_s8:
  endpoint leakage = 0 / 0
  linear_path_rmse = 0.216266
  max_5deg_jump    = 0.302724
  max_5deg_accel   = 0.160076
  monotone         = true
```

업데이트된 basis rule:

```text
Accept candidate basis only if:
  endpoint leakage == 0 or explicitly bounded <= 0.05
  monotone between canonical views
  max_5deg_weight_jump <= ~0.10 before visual tuning
  max_5deg_accel <= ~0.02 before visual tuning
  no alpha-to-zero / no opacity gate
```

이 기준에서는 `cosine_s1`, `linear`, `smoothstep`, `smootherstep`가 후보이고, `cosine_s8`은 중간각 pop 위험 때문에 reject다. 단, shader material 해석을 생각하면 `linear`는 물리 BRDF라기보다 interpolation curve에 가까우므로, implementation spike 1순위는 여전히 `cosine_s1`, 비교군은 `smoothstep/smootherstep`가 맞다.

## D. 업데이트된 추천

1. Row materialization:
   - Iteration 8의 결론 유지: `quantile_max`를 첫 구현 spike로 둔다.
   - 이유는 color 최적화가 아니라 coverage/fair integer materialization/monotone row order다.

2. Directional color:
   - `cosine_s1` 우선 추천 유지.
   - 단, shader spike에는 이번 iteration의 basis gate를 반드시 넣는다: endpoint leakage, max 5° jump, acceleration, monotonicity.
   - `smoothstep/smootherstep`는 물리성은 약하지만 pop 비교군으로 contact sheet에 포함할 가치가 있다.

3. Angular morph:
   - pure color-only 가능 여부는 support classifier로 먼저 판정한다.
   - `create_missing_ratio` 또는 `erase_ratio`가 1%를 넘으면 color-only가 아니라 geometry-needed로 기록한다.
   - micro-displacement는 2~4 px bound 안에서 canonical endpoint displacement=0을 만족할 때만 research 후보로 둔다.

4. 3-view:
   - 이번 iteration은 3-view graph를 더 실행하지 않았다. 기존 iteration 2–5의 결론 유지: arbitrary third image는 실패했고, co-designed `C ⊆ ⋃_y X_y×Z_y` protocol 없이는 production 금지.

## E. 남은 불확실성 / 다음 iteration open questions

1. Browser/WebGL capture: PIL proxy가 아니라 실제 splat/glow/additive shader에서 `cosine_s1` vs fixed blend contact sheet를 찍어야 한다.
2. 실제 intermediate target이 필요하다. 이번 shift test는 stress test일 뿐, 사용자가 원하는 “팔 움직임” 이미지/시퀀스가 있으면 support classifier를 그 target에 직접 적용해야 한다.
3. Micro-displacement solver는 아직 없다. support diff가 1%를 넘는 경우, 그 diff가 작은 boundary displacement로 설명되는지 아니면 새 topology/limb 생성인지 구분하는 matching metric이 필요하다.
4. Quantile row order가 reveal-frame visual artifact를 실제로 줄이는지는 rendered reveal frame에서 확인해야 한다.
5. Directional basis threshold(`jump <= 0.10`, `accel <= 0.02`)는 perceptual calibration 전 임시 기준이다. contact sheet에서 눈으로 pop threshold를 보정해야 한다.

## F. Iteration 9 bottom line

- 새로 강화된 점: “색-only 가능/불가능”을 support set 조건으로 명확히 판정했다. 색 basis는 기존 support 안의 RGB를 바꾸는 도구이고, foreground 생성/삭제는 geometry 또는 opacity-gate 문제다.
- 실제 reference mask 기반 stress test에서 2 px silhouette shift도 missing/erase ratio가 21%로 커져 color-only는 실패한다는 필요한 경고를 얻었다.
- Basis 선택은 `cosine_s1` 유지. `cosine_s8` 같은 sharp lobe는 endpoint가 맞아도 5° jump/accel 때문에 reject한다.
- 남은 최대 공백은 actual WebGL rendered contact sheet와 실제 intermediate target에 대한 support classifier 적용이다.
