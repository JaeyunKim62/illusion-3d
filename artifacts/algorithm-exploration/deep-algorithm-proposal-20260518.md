# Deep algorithm proposal — 2026-05-18

작업 위치: `C:\00_Codes\illusion-3d`
브랜치 확인: `algorithm-exploration-20260518` 맞음.
Production 파일 수정 여부: `src/main.ts`, `scripts/shared-space-harness.mjs` 등 production 파일은 수정하지 않음. 연구용 파일만 `artifacts/algorithm-exploration/`, `artifacts/.hermes/` 아래 작성.
읽은 파일: `README.md`, `CURRENT_HANDOFF.md`, `src/main.ts`, `scripts/shared-space-harness.mjs`.
실행한 throwaway 검증: `artifacts/.hermes/algorithm_exploration_probe_20260518.py` → 결과 `artifacts/.hermes/algorithm_exploration_probe_20260518.json`.

---

## 1. 이번 탐색의 결론

현재 2-view 구현은 “한 row에서 front x와 right z를 임의 pairing해 3D 점 `(x,y,z)`를 만든다”는 점에서 수학적으로는 row-wise bipartite matching/transport의 가장 단순한 특수형이다. 이 방식은 2-view silhouette에는 매우 강하다. 왜냐하면 `x`와 `z`가 같은 row `y`만 공유하면 서로 거의 독립적으로 선택될 수 있기 때문이다. 그러나 per-view color, angle-dependent image 변화, 3-view로 넘어가면 “점 하나가 여러 projection/color/material 관측을 동시에 만족해야 한다”는 multi-marginal constraint 문제가 된다. 특히 3-view는 `A(x,y)`, `B(z,y)`, `C(x,z)`를 동시에 만족하는 3D contingency table / binary tensor feasibility 문제이고, 임의의 세 이미지는 일반적으로 over-constrained다. 따라서 다음 단계의 정답은 projection-only/top/fallback point를 추가하는 것이 아니라, 먼저 exact visual-hull feasibility를 QA로 판정하고, 불가능하면 slack/soft constraint를 명시적으로 수치화하는 solver로 가야 한다. 당장 구현 추천은 “row-wise balanced OT + visual-hull feasibility QA + directional color lobes를 붙일 수 있는 데이터 구조”이며, 병행 연구는 “3-view soft multi-marginal voxel/point solver”다.

---

## 2. 현재 구현과 첨부 이미지 알고리즘의 정확한 차이

### 첨부 이미지 알고리즘

사용자 정의:

```text
A={(x,y): I_A(x,y)=1}
B={(z,y): I_B(z,y)=1}
X_r={x:(x,r)∈A}
Z_r={z:(z,r)∈B}
N_r=min(|X_r|,|Z_r|)
p_k^(r)=(x_k,r,z_k)
P=∪_r {p_k^(r)}
```

핵심은 row `r`에서 양쪽 mask의 active coordinate 수 중 작은 쪽만큼만 점을 만든다는 것이다. 따라서 `|X_r| > |Z_r|`이면 front의 일부 x가 버려지고, `|Z_r| > |X_r|`이면 side의 일부 z가 버려진다. projection은 깨끗하지만 더 넓은 view의 coverage가 감소한다.

### 현재 repo 구현

`src/main.ts` 기준 현재 구현은 다음이다.

```text
frontSamples = front.rows[row]
sideSamples  = side.rows[row]
if either empty: skip row
shuffle both deterministically
count = max(frontSamples.length, sideSamples.length)
for i in [0,count):
  x = frontSamples[i mod |frontSamples|].coord
  z = -sideSamples[i mod |sideSamples|].coord
  y = rowToY(row)
  color = fixed shared-space blend(frontColor, sideColor)
```

차이:

1. `N_r=min`이 아니라 `N_r=max`다.
2. 짧은 쪽 row sample을 modulo로 재사용한다.
3. 따라서 긴 쪽 active coordinate는 훨씬 덜 버려지고, 짧은 쪽은 같은 projection 위치에 여러 depth/partner가 생긴다.
4. mask의 active vertical bounds를 각 이미지별로 찾아 `ROW_COUNT` 범위에 정규화한다. 즉 원본 y좌표 그대로가 아니라 active region끼리 row를 맞춘다.
5. `z`는 Three.js +X 카메라 screen convention 때문에 부호 반전한다.
6. 색은 point마다 하나의 고정 RGB attribute다. 현재 shader는 glow/splat만 하고, view별 opacity gate, depth gate, texture swap, projection-only/top/fallback 점은 없다.
7. `scripts/shared-space-harness.mjs`는 top/projection-only 회귀를 명시적으로 금지한다.

### 작은 synthetic probe 결과

`artifacts/.hermes/algorithm_exploration_probe_20260518.json`에서 synthetic mask로 확인한 row policy 결과:

```text
min:        points=892,  front_iou=0.7757, side_iou=0.9331
max_reuse:  points=1194, front_iou=1.0000, side_iou=0.9791, duplicate_front=44, duplicate_side=258
balancedOT: points=1194, front_iou=1.0000, side_iou=0.9791, duplicate_front=44, duplicate_side=258
```

이 probe는 silhouette coverage만 보므로 current max+reuse와 quantile OT가 동일 IoU로 나온다. 하지만 실제 image/color에서는 pairing order가 중요하므로 modulo shuffle은 color/shape coherence를 쉽게 깨고, OT/monotone matching은 row 내부의 left-to-right coherence를 더 잘 보존할 가능성이 높다.

---

## 3. 알고리즘 후보 7개

### 후보 1 — Row-wise min bipartite matching

핵심 수식:

```text
For each row r:
  X_r={x_i}, Z_r={z_j}
  N_r=min(|X_r|,|Z_r|)
  choose matching M_r ⊂ X_r×Z_r, |M_r|=N_r
  P_r={(x,r,z):(x,z)∈M_r}
```

matching cost는 단순 index matching, random matching, 또는 color/curvature-aware cost를 둘 수 있다.

```text
min_M Σ_(i,j∈M) c_r(i,j)
where c_r = λ_pos |q_i-q_j| + λ_color ||a_i-b_j|| + λ_curv Δlocal
```

- 푸는 제약: 모든 점이 두 view에 동시에 존재한다. projection-only noise가 없다.
- 포기하는 제약: 더 많은 active pixel을 가진 view의 초과 mass는 버린다.
- 2-view 적용성: 높음. 첨부 이미지 알고리즘과 동일 계열.
- per-view color 적용성: 낮음~중간. 점 하나에 색 하나만 두면 두 view 색이 충돌한다. matching cost로 비슷한 색끼리 pair하면 완화된다.
- angular change 적용성: 낮음. geometry가 sparse해지고 버려진 silhouette가 많아 중간각 변화 여지가 작다.
- 3-view 적용성: 낮음. top `C(x,z)`까지 만족하려면 matching edge `(x,z)`가 `C` 안에 있어야 하므로 각 row의 bipartite graph가 크게 희소해진다.
- failure mode: row별 width mismatch가 큰 이미지에서 한쪽 silhouette가 잘린다. thin limbs/ears/feet가 사라질 수 있다.
- 검증 실험: min/max/OT row matching 비교에서 projection IoU, active coverage, row drop, thin-structure recall 측정.
- 난이도/추천도: 난이도 낮음, 추천도 낮음. baseline/ablation용으로만 유지.

### 후보 2 — Current max+reuse shared row product-lite

핵심 수식:

```text
N_r=max(|X_r|,|Z_r|)
p_i^r=(X_r[i mod |X_r|], r, Z_r[i mod |Z_r|])
```

- 푸는 제약: 긴 쪽 view의 silhouette coverage를 보존한다. point count가 충분해진다.
- 포기하는 제약: 짧은 쪽 projection coordinate를 중복 사용한다. 이는 density imbalance와 row banding을 만든다.
- 2-view 적용성: 현재 증명된 practical baseline. clean 2-view에는 좋다.
- per-view color 적용성: 고정 RGB blend만 가능하면 color conflict가 남는다. 같은 front pixel이 여러 side color와 pair될 수 있어 front color가 혼탁해질 수 있다.
- angular change 적용성: geometry 고정 상태에서 색/재질만 바꾸는 경우에는 가능하지만 silhouette morph는 어렵다.
- 3-view 적용성: 그대로는 낮음. top `C(x,z)`를 고려하지 않으므로 `P`의 top projection이 우연히 맞지 않으면 barcode/noise가 된다.
- failure mode: modulo reuse가 주기적 artifact를 만들 수 있다. shuffle으로 완화하지만 spatial continuity가 약하다. 3-view를 naïve하게 추가하면 forbidden projection-only temptation이 생긴다.
- 검증 실험: 현재 방식과 OT 방식의 canonical render IoU/LPIPS-like simple metric, row banding frequency, color RMSE 비교.
- 난이도/추천도: 난이도 매우 낮음, 추천도 중간. 현재 contest artifact 유지용. 확장용 backbone으로는 보강 필요.

### 후보 3 — Row-wise balanced optimal transport / quantile matching

핵심 수식:

각 row를 1D empirical distributions로 본다.

```text
μ_r = Σ_i a_i δ_{x_i}
ν_r = Σ_j b_j δ_{z_j}
Find transport plan T_r ≥ 0
  Σ_j T_ij ≤ a_i, Σ_i T_ij ≤ b_j
  total mass τ_r = min/max/target mass
  minimize Σ_ij T_ij c_ij + ε Σ_ij T_ij(log T_ij - 1)
```

point materialization:

```text
For each nonzero T_ij, instantiate n_ij = round(κ T_ij) points at (x_i, r, z_j)
```

unbalanced variant:

```text
min_T <C,T> + ε KL(T) + ρ KL(T1 || μ) + ρ KL(T^T1 || ν)
```

- 푸는 제약: row별 mass mismatch를 명시적으로 다룬다. modulo reuse보다 왜 중복/삭제가 생기는지 설명 가능하다.
- 포기하는 제약: exact binary pixel coverage와 fixed point budget을 동시에 만족하기 어렵다. rounding이 필요하다.
- 2-view 적용성: 매우 높음. 현재 구현을 수학적으로 정리하는 가장 자연스러운 다음 단계.
- per-view color 적용성: 중간~높음. cost에 `||colorA_i-colorB_j||`, edge/saliency weight를 넣어 색 충돌이 덜한 pair를 선호할 수 있다. 단, point color 하나 문제를 완전히 해결하진 못한다.
- angular change 적용성: 중간. transport plan이 left-right continuity를 보존하면 중간각에서 random cloud가 덜 깨진다.
- 3-view 적용성: 중간. 각 row에서 top mask가 허용하는 edge만 남기는 constrained bipartite matching으로 확장 가능하다:

```text
T_ij = 0 if C(x_i,z_j)=0
```

- failure mode: `C` constraint가 너무 강하면 row graph가 disconnected되어 front/side coverage가 크게 떨어진다. entropic OT가 너무 퍼지면 blur/density noise가 생긴다.
- 검증 실험: min/max/OT 비교. metric은 projection IoU, coverage, point count, duplicate multiplicity entropy, row continuity, color RMSE.
- 난이도/추천도: 난이도 중간, 추천도 높음. 지금 당장 구현할 1순위.

### 후보 4 — Exact 3-view visual hull voxel solver

핵심 수식:

세 binary target:

```text
A ⊂ X×Y, B ⊂ Z×Y, C ⊂ X×Z
Find binary tensor V_xyz ∈ {0,1}
Projection constraints:
  A_xy = OR_z V_xyz
  B_zy = OR_x V_xyz
  C_xz = OR_y V_xyz
```

가장 보수적인 candidate set은 visual hull:

```text
H = {(x,y,z): A(x,y)=1 ∧ B(z,y)=1 ∧ C(x,z)=1}
```

그리고 exact feasibility는 다음 projection equalities가 모두 성립해야 한다.

```text
π_xy(H)=A, π_zy(H)=B, π_xz(H)=C
```

- 푸는 제약: projection-only 없이 세 view를 동시에 만족하는지 exact하게 판정한다.
- 포기하는 제약: 임의 세 이미지가 가능하다고 가정하지 않는다. 불가능하면 불가능하다고 말한다.
- 2-view 적용성: 2-view는 `C`가 없으므로 row product/hull이 항상 훨씬 쉽다.
- per-view color 적용성: geometry feasibility와 별도. color는 `V` 위에 angular material을 얹어야 한다.
- angular change 적용성: 낮음~중간. exact canonical silhouettes는 보존하지만 중간각 silhouette는 uncontrolled visual hull projection이므로 QA 필요.
- 3-view 적용성: 높음, 단 exact 가능 이미지에 한정.
- failure mode: compatible한 top을 고르지 않으면 missing projection pixels가 생긴다. 반대로 top을 너무 넓히면 point count가 폭증하고 reveal에서 부피가 뭉개진다.
- 검증 실험: synthetic front/right/top mask로 `|H|`, `IoU(πH,A/B/C)`, missing/extra pixel, density histogram 측정.
- 난이도/추천도: 난이도 중간, 추천도 높음 for QA. production visual로 바로 쓰기보다는 feasibility gate로 먼저.

Probe 결과:

```text
compatible_top_cutout: voxels=33597, front_iou=1.0000, side_iou=0.9791, top_iou=1.0000
bad diagonal top:       voxels=7436,  front_iou=0.8339, side_iou=0.9603, top_iou=0.9827
bad top slack r=8:      front_iou=1.0000, side_iou=0.9791, top_iou=0.7761
```

해석: top slack을 키우면 front/side는 회복되지만 top fidelity가 급격히 무너진다. 이것이 3-view의 핵심 trade-off다.

### 후보 5 — Soft 3-view multi-marginal occupancy optimization

핵심 수식:

binary OR projection은 최적화가 어렵다. relaxed occupancy `v_xyz∈[0,1]`로 둔다.

```text
Π_A(v)_xy = 1 - Π_z (1 - v_xyz)       # differentiable OR
Π_B(v)_zy = 1 - Π_x (1 - v_xyz)
Π_C(v)_xz = 1 - Π_y (1 - v_xyz)

min_v
  λA L(Π_A(v), A) + λB L(Π_B(v), B) + λC L(Π_C(v), C)
  + λs Σ v_xyz                         # sparsity
  + λtv TV(v) or density smoothness
  + λocc occlusion/noise penalty
subject to 0≤v≤1, optional v=0 outside visual hull dilations
```

대안으로 count projection을 써도 된다.

```text
Π_A^count(v)_xy = Σ_z v_xyz
Target count can be binary/saturating: min(1, count)
```

- 푸는 제약: over-constrained 3 images에서 “얼마나 불가능한지”와 “어떤 view를 얼마나 희생할지”를 수치화한다.
- 포기하는 제약: exact binary physical point set을 바로 보장하지 않는다. threshold/sampling 단계가 필요하다.
- 2-view 적용성: 가능하지만 과하다.
- per-view color 적용성: 높음. occupancy와 별도로 각 occupied point에 angular color basis coefficient를 optimize할 수 있다.
- angular change 적용성: 높음. canonical + intermediate view loss를 추가할 수 있다.
- 3-view 적용성: 매우 높음. 실제로 필요한 최종 연구 방향.
- failure mode: soft loss가 낮아도 sampled point cloud에서 speckle/noise가 생길 수 있다. density regularization을 잘못 주면 image가 blur된다. compute cost가 증가한다.
- 검증 실험: exact visual hull이 실패하는 synthetic case에서 slack radius/λ weights sweep. acceptance는 canonical IoU, extra noise, point budget, density entropy.
- 난이도/추천도: 난이도 높음, 추천도 중간~높음. 병행 연구용.

### 후보 6 — Directional color basis / anisotropic BRDF point

핵심 수식:

geometry는 고정하고, point color만 view direction `ω`의 함수로 둔다.

```text
c_i(ω) = clamp( Σ_m β_im φ_m(ω) )
```

basis 예시:

```text
lobe basis: φ_m(ω)=max(0, n_m·ω)^s
spherical harmonics: φ_lm(ω)=Y_lm(ω)
learned MLP/basis: φ_m(ω)=MLP_m(ω) but coefficients fixed per point
```

per-view target fitting:

```text
For canonical view v with direction ω_v and point i projected to pixel u:
  minimize Σ_v Σ_i visible w_i,v || c_i(ω_v) - target_v(π_v(p_i)) ||²
```

- 푸는 제약: 점 하나가 view별로 다른 색을 보일 수 있다. 이것은 texture swap/opacity gate가 아니라 directional reflectance/material로 정당화할 수 있다.
- 포기하는 제약: silhouette/occupancy는 바뀌지 않는다. 색만 바뀐다.
- 2-view 적용성: 높음. front lobe와 right lobe 두 개만으로도 goose/nubzuki 색을 분리 가능하다.
- per-view color 적용성: 매우 높음. 현재 fixed blend보다 본질적으로 낫다.
- angular change 적용성: 중간. target image의 작은 color 변화는 가능하다. silhouette 변화는 불가 또는 제한적.
- 3-view 적용성: 높음. lobe를 3개 이상 둔다. 단 중간각 smoothness QA가 필수.
- failure mode: lobe sharpness가 너무 크면 사실상 view switch처럼 보이고 중간각에서 pop이 생긴다. 너무 낮으면 색이 섞인다.
- 검증 실험: view별 target color RMSE, canonical silhouette 유지, 중간각 `||c(θ+δ)-c(θ)||` smoothness, lobe leakage 측정.
- 난이도/추천도: 난이도 중간, 추천도 높음. per-view color 요구에 가장 직접 대응.

Probe의 lobe toy 결과는 sharpness `s=8`에서 0°/90° endpoint error는 0이지만 30°/60° 중간에서 linear target 대비 RMSE 0.2295가 생겼다. 즉 basis 선택과 중간각 target 정의를 QA해야 한다.

### 후보 7 — Angular morph with micro-displacement / multi-lobe impostor points

핵심 수식:

점의 base position은 유지하되, view direction에 따라 작은 displacement를 허용한다.

```text
p_i(ω)=p_i^0 + Σ_m d_im ψ_m(ω)
with constraints:
  p_i(ω_front) projects to A_front
  p_i(ω_right) projects to B_right
  ||d_im|| ≤ ε or only tangent-plane displacement
```

더 강한 방식은 여러 angular lobes를 둔다.

```text
point i has lobes ℓ:
  color c_iℓ, offset d_iℓ, angular weight a_iℓ(ω)
render contribution = Σℓ a_iℓ(ω) splat(p_i+d_iℓ, c_iℓ)
```

- 푸는 제약: “팔이 조금 움직인다” 같은 angular-dependent image 변화 일부를 표현할 수 있다.
- 포기하는 제약: 엄격한 fixed geometry invariant가 약해진다. 만약 displacement가 카메라 view에 따라 바뀌면 물리 점 위치가 변하는 셈이라 contest concept에서 위험하다.
- 2-view 적용성: 제한적으로 가능. canonical view에서는 displacement가 0이 되도록 강제해야 한다.
- per-view color 적용성: lobe color와 함께 쓰면 높음.
- angular change 적용성: 높음 for small local motion. 하지만 silhouette change가 크면 필요 displacement가 커져 물리적 정당성이 약해진다.
- 3-view 적용성: 낮음~중간. canonical 3-view exact를 먼저 맞춘 뒤 intermediate-only effect로 제한해야 한다.
- failure mode: view-dependent geometry gate처럼 보일 수 있다. canonical image는 맞아도 reveal에서 fake가 드러난다. 팔 silhouette 변화가 크면 occlusion/geometry가 필요하다.
- 검증 실험: canonical view IoU drop ≤ 1%, intermediate target IoU gain, max displacement/pixel, temporal smoothness, reveal artifact score.
- 난이도/추천도: 난이도 높음, 추천도 보류. 색/BRDF로 안 되는 silhouette-only case에 한해 연구.

---

## 4. 3-view exact/soft feasibility — 가장 중요한 섹션

### 4.1 문제 정의

3-view target을 다음 binary set으로 둔다.

```text
A ⊂ X×Y   # front projection, screen coordinate (x,y)
B ⊂ Z×Y   # right projection, screen coordinate (z,y)
C ⊂ X×Z   # top projection, screen coordinate (x,z)
```

찾고 싶은 것은 3D 점/voxel set `P ⊂ X×Y×Z`다.

```text
π_xy(P)=A
π_zy(P)=B
π_xz(P)=C
```

binary voxel occupancy로 쓰면:

```text
V_xyz ∈ {0,1}
A_xy = OR_z V_xyz
B_zy = OR_x V_xyz
C_xz = OR_y V_xyz
```

이것은 2-view보다 훨씬 강하다. 2-view에서는 row `y`마다 `X_y`와 `Z_y`가 모두 non-empty면 Cartesian product 또는 matching으로 얼마든지 `(x,y,z)`를 만들 수 있다. 즉 row alignment만 맞으면 된다. 그러나 3-view에서는 `(x,z)` pair가 top `C`에도 존재해야 하므로 row-wise bipartite graph의 allowed edges가 `C`로 제한된다.

### 4.2 Exact feasibility의 필요충분 조건

candidate visual hull을 정의한다.

```text
H = {(x,y,z): A_xy=1 ∧ B_zy=1 ∧ C_xz=1}
```

모든 exact solution `P`는 반드시 `H`의 subset이다. 왜냐하면 어떤 voxel이 켜져 있으면 그 세 projection pixel도 모두 target 안에 있어야 extra noise가 생기지 않기 때문이다.

따라서 exact feasibility의 필요충분 조건은 다음이다.

```text
π_xy(H)=A  and  π_zy(H)=B  and  π_xz(H)=C
```

증명 스케치:

- 필요: exact `P`가 존재한다고 하자. extra pixel이 없어야 하므로 `P⊂H`. 그러면 `π(P)⊂π(H)`. 동시에 exact라서 `π(P)=A/B/C`. 따라서 target은 `π(H)`에 포함되어야 한다. 반대로 `H` 자체의 projection은 정의상 target 밖으로 나갈 수 없으므로 `π(H)⊂A/B/C`. 따라서 같아야 한다.
- 충분: 위 equalities가 성립하면 `P=H`를 선택하면 세 projection이 정확히 target과 같다.

즉 exact feasibility QA는 solver보다 먼저 가능하다. `H`를 만들고 projection IoU/missing/extra를 계산하면 된다.

### 4.3 Row-wise graph 관점

각 `y` row에서:

```text
X_y = {x: A_xy=1}
Z_y = {z: B_zy=1}
Allowed edge E_y = {(x,z): x∈X_y, z∈Z_y, C_xz=1}
```

front pixel `(x,y)`가 살아나려면:

```text
∃ z∈Z_y such that (x,z)∈C
```

right pixel `(z,y)`가 살아나려면:

```text
∃ x∈X_y such that (x,z)∈C
```

top pixel `(x,z)`가 살아나려면:

```text
∃ y such that x∈X_y and z∈Z_y and C_xz=1
```

이 세 조건이 모두 필요하다. 특히 top pixel은 어떤 row `y`에서 front가 x를 가지고 side가 z를 가져야 한다. 즉 `C`의 모든 active `(x,z)`가 적어도 하나의 compatible y를 가져야 한다.

### 4.4 왜 임의의 3개 이미지가 over-constrained인가

2-view는 row별로 두 1D set을 연결하면 된다. 하지만 3-view는 `C`가 모든 row의 allowed edge를 공통으로 제한한다. 예를 들어 front의 어떤 row에 `x=10`이 있고 side 같은 row에 `z=20`이 있어도, top `C(10,20)=0`이면 그 조합은 금지된다. 반대로 top `C(10,20)=1`이어도 `x=10`과 `z=20`이 같은 y에서 동시에 active인 row가 하나도 없으면 해당 top pixel은 만들 수 없다.

따라서 세 이미지를 독립적으로 고르면 다음 문제가 생긴다.

1. front/right의 same-y support가 top의 x-z pattern을 생성하지 못한다.
2. top이 허용한 edge가 너무 적어 front/right row coverage가 떨어진다.
3. top을 넓혀 front/right를 살리면 top projection이 두꺼워지거나 흐려진다.
4. sparse exact solution은 canonical에서는 맞아도 reveal에서 너무 비어 보이고, dense hull solution은 reveal에서 덩어리가 커진다.

Throwaway probe에서도 over-constrained diagonal top은 front IoU가 0.8339로 떨어졌다. top slack dilation radius를 키우면 front IoU는 1.0까지 회복되지만 top IoU는 0.7761까지 떨어졌다.

### 4.5 Exact 3-view를 위한 QA 강제 조건

projection-only noise 없이 3-view를 추가하려면 최소한 다음 QA를 production gate로 강제해야 한다.

```text
projectionCount = 3
projectionOnlyPointCount = 0
noProjectionOnlyPoints = true
for every point p=(x,y,z): A(x,y)=1 and B(z,y)=1 and C(x,z)=1
frontProjectionIoU ≥ threshold, sideProjectionIoU ≥ threshold, topProjectionIoU ≥ threshold
missingFrontPixels, missingSidePixels, missingTopPixels reported
extraFront/Side/Top must be 0 for exact mode
point count and per-cell density bounded
```

중요한 것은 top view 버튼을 다시 넣기 전에 `C`를 만족하지 않는 점을 절대 추가하지 않는 것이다. 이전 실패의 핵심은 top projection-only point가 front/right에서 barcode-like background noise를 만들었다는 점이다.

### 4.6 Soft constraint 설계

Exact가 실패할 때 선택지는 “속이는 점 추가”가 아니라 soft feasibility mode다.

#### Slack dilation

각 target을 radius `s_v`만큼 dilation해서 relaxed hull을 만든다.

```text
H_s={(x,y,z): d((x,y),A)≤s_A ∧ d((z,y),B)≤s_B ∧ d((x,z),C)≤s_C}
```

그리고 원 target projection IoU와 slack 사용량을 같이 보고한다.

```text
slackCost = mean distance of occupied projection to nearest target pixel
```

#### Weighted view loss

view마다 중요도를 둔다.

```text
min_P λA L(π_xy(P),A)+λB L(π_zy(P),B)+λC L(π_xz(P),C)+regularizers
```

예: contest artifact가 front/right를 더 중시하면 `λA=λB>λC`를 둘 수 있지만, 보고서에는 top이 soft임을 명확히 밝혀야 한다.

#### Sparsity and density regularization

```text
λs |P| + λvar Var_y,row(counts) + λnn nearest-neighbor penalty
```

- sparsity가 너무 강하면 canonical image에 holes가 생긴다.
- density가 너무 강하면 reveal이 뭉개진다.
- row/voxel density histogram을 metric으로 둬야 한다.

#### Occlusion model

현재 point cloud는 additive splat에 가깝고 strict occlusion을 활용하지 않는다. 3-view에서 occlusion을 도입하면 특정 view에서 앞점이 뒤점을 가려 projection을 조절할 수 있지만, 이것은 depth gate/opacity gate와 경계가 위험하다. 허용하려면 물리적으로 일관된 opaque splat/mesh occlusion이어야 하고, view별로 점을 끄면 안 된다.

### 4.7 3-view exact/soft의 추천 운영 방식

1. `exact-vh` mode: visual hull feasibility만 판단. exact pass하면 3-view 후보로 채택.
2. `soft-vh` mode: dilation/slack을 허용하고 slack metric을 노출. canonical 3-view demo가 아니라 research mode로 표시.
3. `optimized-soft` mode: relaxed occupancy optimization. acceptance criteria가 통과될 때만 production 편입.

---

## 5. 색/재질 feasibility: view별 다른 색의 정당화

현재 fixed RGB blend는 한 점이 어떤 방향에서도 같은 색을 낸다는 모델이다. view별 다른 색을 내려면 다음 중 하나여야 한다.

### 허용 가능한 물리/렌더링 해석

1. Directional BRDF:
   - 점 표면이 방향에 따라 다른 반사 스펙트럼을 낸다.
   - `c_i(ω)=BRDF_i(ω_l,ω_o)`로 표현.
2. Anisotropic splat:
   - 점이 작은 oriented disk/ellipsoid이고 관측 방향에 따라 보이는 normal/lighting이 달라진다.
3. Micro-lenticular/louvered point:
   - 한 점 안에 매우 작은 lenticular/louver structure가 있어 viewing angle별 색 lobe가 다르다.
   - contest concept과도 가장 잘 맞는다.
4. Angular color basis:
   - 구현상은 shader에서 view direction basis를 평가한다.
   - 물리 해석은 micro-lenticular BRDF로 둔다.
5. Spherical harmonics / learned basis:
   - low-frequency smooth change에는 SH, sharp view separation에는 lobe basis가 낫다.

### 금지/위험한 경계

- View별 texture swap: 카메라가 front면 goose texture, right면 nubzuki texture를 직접 바꾸는 것은 fake에 가깝다.
- View별 opacity gate: 특정 view에서 특정 점을 끄는 것은 projection-only와 유사한 cheating risk가 있다.
- Depth gate: canonical camera에서만 보이도록 depth-test/clip을 조작하면 physical cloud invariant가 약해진다.

### 색 변화와 geometry/opacity 변화의 경계

- 색 변화: 같은 point, 같은 position, 같은 existence. `color=f(direction)`만 변한다. silhouette support는 유지된다.
- 재질 변화: color뿐 아니라 specular/glow size가 direction에 따라 변할 수 있다. 단 alpha를 0으로 떨어뜨려 점을 사실상 제거하면 opacity gate로 간주해야 한다.
- geometry 변화: point position 또는 occupied set이 direction에 따라 바뀐다. “팔 silhouette가 이동”처럼 projection support 자체가 달라지면 색만으로는 불충분하다.

---

## 6. Angular change / animation feasibility

### 수식화

view direction을 `θ`로 두고 target image를 `I_{v,θ}`라 하자.

```text
Given fixed points P={p_i}
render R(P, material(θ), camera(θ)) ≈ I_θ
```

canonical constraints:

```text
R(θ_front)=I_front,0
R(θ_right)=I_right,0
R(θ_top)=I_top,0  # if 3-view
```

작은 변화 target:

```text
I_θ = I_canonical + ΔI(θ)
```

### 세 선택지 비교

#### A. 고정 위치 + color/material만 변화

```text
p_i fixed
c_i=c_i(θ)
```

- 장점: invariant 보존이 가장 쉽다.
- 가능: 색 변화, 작은 shading 변화, 내부 texture 변화.
- 불가능/취약: silhouette support가 바뀌는 팔 이동.

#### B. Micro-displacement 허용

```text
p_i(θ)=p_i^0 + δ_i(θ), ||δ_i||≤ε
```

- 장점: 작은 contour 흔들림, limb wiggle 가능.
- 위험: view-dependent geometry로 보일 수 있다.
- 조건: canonical view에서는 `δ=0`, displacement bound와 smoothness QA 필수.

#### C. Multiple angular lobes

```text
contribution_i(θ)=Σ_l a_il(θ) splat(p_i+d_il, c_il)
```

- 장점: lenticular card처럼 각도별 sub-image를 표현 가능.
- 위험: `a_il`이 opacity gate처럼 작동할 수 있다. alpha를 완전히 끄는 대신 BRDF lobe energy로 정당화해야 한다.

### “팔이 움직인다” 판단

팔 움직임이 단순히 색/명암 패턴 이동이면 directional color basis로 가능하다. 그러나 팔의 외곽선이 다른 위치로 이동해서 silhouette support가 달라지는 경우, 색만으로는 배경에 팔을 새로 만들거나 기존 팔을 지워야 하므로 사실상 opacity/geometry 변화가 필요하다. 이 경우 권장 순서는:

1. canonical silhouette는 fixed geometry로 보존.
2. 중간각에서만 micro-displacement `ε`를 작게 허용.
3. 변화량 metric을 제한: canonical IoU drop ≤ 1%, max projected displacement ≤ 2~4 px.
4. 크고 명확한 limb animation은 보류.

---

## 7. 실제 다음 1주일 spike 계획

Production source를 바로 바꾸지 말고 `scripts/` 또는 `artifacts/.hermes/`에서 executable experiments를 먼저 만든다. 이후 통과한 것만 `src/main.ts`로 최소 이식한다.

### Day 1 — Row matching policy 비교

파일 초안:

```text
scripts/experiment-row-matching.mjs       # production 편입 전에는 artifacts/.hermes로 시작 가능
artifacts/algorithm-exploration/row-matching-results-202605xx.json
```

입력:

```text
artifacts/reference-image/goose.png
artifacts/reference-image/cake.png or nubzuki.png
same mask extraction parameters as src/main.ts
policies: min, current max+reuse, quantile OT, color-aware OT
```

출력:

```text
projection IoU front/right
coverage front/right
point count
duplicate multiplicity per projected pixel
row density min/median/max
color conflict RMSE before directional shader
optional preview PNG/contact sheet
```

Acceptance:

```text
OT policy keeps front/right IoU within 1% of current max+reuse
duplicate entropy improves or row banding metric decreases
color conflict RMSE lower than current blend pairing
no projectionOnly points
```

### Day 2 — 3-view visual hull feasibility

파일 초안:

```text
scripts/experiment-3view-visual-hull.mjs
artifacts/algorithm-exploration/3view-visual-hull-results-202605xx.json
```

입력:

```text
front=goose.png
right=cake/nubzuki.png
top candidates=phoenix.png/kumdori.png/synthetic generated compatible top
resolution sweep: 64×48×64, 96×64×96, 128×80×128
```

출력:

```text
|H| voxel count
π_xy/π_zy/π_xz IoU
missing/extra pixels per view
row graph isolated x/z count
compatible top pixel ratio
point budget estimate after sampling H
```

Acceptance:

```text
Exact mode: all three IoU ≥ 0.98 and extra=0, missing small enough for visual legibility
Soft mode: report slack explicitly; no production top view if top IoU < 0.90 or front/right degrade > 2%
```

### Day 3 — Directional color shader QA

파일 초안:

```text
scripts/experiment-directional-color.mjs
artifacts/algorithm-exploration/directional-color-results-202605xx.json
```

입력:

```text
fixed 2-view point cloud from selected row policy
front/right sampled target RGB per point
basis: two-lobe, three-lobe, SH order 1/2
sharpness sweep s={2,4,8,16}
```

출력:

```text
front color RMSE
right color RMSE
mid-angle smoothness = mean ||c(θ+Δ)-c(θ)||
leakage = color contribution from wrong canonical lobe
canonical alpha never zero check
```

Acceptance:

```text
front/right color RMSE improves ≥ 25% over fixed blend
mid-angle smoothness no visible pop: max ΔE/RMSE step below threshold
no alpha/opacity gate; color basis only
```

### Day 4 — Angular morph feasibility

파일 초안:

```text
scripts/experiment-angular-morph.mjs
artifacts/algorithm-exploration/angular-morph-results-202605xx.json
```

입력:

```text
canonical front/right masks
synthetic intermediate targets: small arm shift, color-only arm shift, silhouette arm shift
micro-displacement ε sweep
```

출력:

```text
canonical IoU before/after
intermediate target IoU gain
max/mean projected displacement
temporal smoothness
number of points requiring large displacement
```

Acceptance:

```text
canonical IoU drop ≤ 1%
intermediate IoU gain meaningful ≥ 0.05
max displacement ≤ 2~4 px for acceptable physical plausibility
If silhouette shift requires >4 px, classify as geometry-needed and defer.
```

### Day 5 — Browser prototype branch decision

- If Day 1+3 pass: implement row OT + directional color basis in `src/main.ts` behind simple constants.
- If Day 2 exact 3-view passes on a chosen top image: add 3-view only with visual hull point set and harness update.
- If Day 2 only soft-passes: do not add production top button; keep research artifact.

### Day 6 — Visual evidence generation

```text
front/right/reveal PNGs
mid-angle color smoothness contact sheet
3-view exact/soft feasibility table
```

Acceptance:

```text
QA JSON + screenshots agree
no console errors
harness updated only if production behavior changes
```

### Day 7 — Merge recommendation

- Write concise Korean status and before/after metrics.
- If directional color improves but morph/3view remains research, merge only color/row OT.
- Keep 3-view/morph out unless exact feasibility is numerically proven.

---

## 8. 최종 추천

### 지금 당장 구현할 알고리즘 1개

Row-wise balanced OT / quantile matching + color-aware cost.

이유:

- 현재 max+reuse 구현의 자연스러운 수학적 upgrade다.
- production invariant를 깨지 않는다.
- 2-view quality, color pairing, row banding을 동시에 개선할 가능성이 있다.
- 이후 3-view constrained edge `C(x,z)=1`로 확장 가능하다.

### 병행 연구 1개

Directional color basis / micro-lenticular BRDF shader.

이유:

- “각 이미지마다 다른 색” 요구를 fixed RGB blend보다 정직하게 해결한다.
- opacity gate/texture swap이 아니라 material model로 설명할 수 있다.
- canonical 2-view에는 바로 유효하고, 3-view에도 basis lobe만 추가하면 확장된다.

### 보류 1개

View-dependent micro-displacement / angular silhouette morph.

이유:

- 팔 움직임이 silhouette 변화라면 색만으로는 불가능하다.
- displacement는 physical point invariant를 약화시킬 위험이 있다.
- canonical 보존/중간각 개선/physical plausibility metric이 먼저 필요하다.

### 3-view에 대한 최종 판단

3-view는 “이미지 하나 더 넣고 top point를 추가”하는 문제가 아니다. exact visual hull feasibility gate를 통과한 top image만 production에 넣어야 한다. 임의 top image가 over-constrained이면 soft mode로 연구해야 하며, 그 경우에는 slack, missing pixels, density/noise를 사용자에게 명확히 보여줘야 한다. projection-only noise 없이 3-view를 추가하는 최소 조건은 `H={(x,y,z):A∧B∧C}`의 세 projection이 target과 충분히 일치한다는 QA 통과다.
