# Verification plan — algorithm exploration 2026-05-18

목표: production source를 바로 바꾸기 전에 현재 2-view shared point cloud의 확장 가능성을 executable experiment로 검증한다.

Production 파일 수정 금지 원칙:

```text
Do not modify src/main.ts during experiments.
Do not add top/projection-only/fallback points to production.
Write outputs under artifacts/algorithm-exploration/.
Throwaway scripts can live under artifacts/.hermes/ first.
Only after acceptance, promote selected script to scripts/ and selected implementation to src/main.ts.
```

현재 throwaway probe:

```text
artifacts/.hermes/algorithm_exploration_probe_20260518.py
artifacts/.hermes/algorithm_exploration_probe_20260518.json
```

---

## Experiment 1. Row matching policy 비교

### 질문

현재 `max+reuse`가 쉬운 2-view silhouette에는 좋지만, modulo reuse가 color conflict/row banding을 악화시키는가? `min`, `max+reuse`, `balanced OT`, `color-aware OT`를 같은 mask extraction 위에서 비교한다.

### 입력

```text
front image: artifacts/reference-image/goose.png
right image: artifacts/reference-image/cake.png or nubzuki.png
mask params: MASK_WIDTH=960, MASK_HEIGHT=280, ROW_COUNT=190, SAMPLE_STRIDE=1
policies:
  - min
  - current max+reuse random shuffle
  - quantile balanced OT
  - color-aware OT
```

### 의사코드

```js
for image in [front, right]:
  rows = extractColorRowsLikeMainTs(image)

for policy of policies:
  points = []
  for r in rows:
    X = frontRows[r]
    Z = sideRows[r]
    if empty(X) or empty(Z): continue

    if policy == 'min':
      M = match first/quantile min(|X|, |Z|)

    if policy == 'max_reuse':
      N = max(|X|, |Z|)
      M = [(X[i % |X|], Z[i % |Z|]) for i in 0..N-1]

    if policy == 'balanced_ot':
      N = max(|X|, |Z|)
      M = quantileMatch(X, Z, N)

    if policy == 'color_aware_ot':
      cost(i,j) = λq * abs(qX_i - qZ_j)
                + λc * rgbDistance(frontColor_i, sideColor_j)
                + λe * edge/saliencyMismatch(i,j)
      T = sinkhornOrHungarian(X, Z, cost, unbalanced=true)
      M = materialize(T)

    points.push((x, rowToY(r), -z, frontColor, sideColor))

  render/projection-rasterize points to front/right masks
  compute metrics
  write JSON + optional preview PNG
```

### Metric

```text
frontProjectionIoU, rightProjectionIoU
frontCoverage, rightCoverage
pointCount
rowDensity min/median/max
matchedRowRatio
duplicateMultiplicity mean/max per projected pixel
rowBandingScore = variance of per-row point counts after normalization
pairColorConflict = mean ||frontRGB - sideRGB|| for matched pairs
fixedBlendFrontRMSE, fixedBlendRightRMSE
```

### 성공 기준

```text
balanced/color-aware OT front/right IoU within 1% of current max+reuse
pairColorConflict decreases by >= 10% or fixedBlend RMSE decreases
rowBandingScore does not worsen
projectionOnlyPointCount remains 0
```

### 실패 판정

```text
front/right IoU drops > 2%
thin structure recall visibly worsens
OT creates too few points or severe row holes
```

---

## Experiment 2. 3-view visual hull feasibility

### 질문

front/right/top 세 binary image가 projection-only noise 없이 하나의 3D point/voxel set으로 동시에 가능한가?

### 입력

```text
A: front mask, e.g. goose.png
B: right mask, e.g. cake.png or nubzuki.png
C candidates:
  - synthetic compatible top generated from A/B
  - artifacts/reference-image/phoenix.png
  - artifacts/reference-image/kumdori.png
  - any user-chosen third image
resolution sweep:
  64×48×64
  96×64×96
  128×80×128
```

### 의사코드

```js
A = binaryMaskXY(front)
B = binaryMaskZY(right)
C = binaryMaskXZ(top)

H = []
for y in Y:
  Xy = [x where A[x,y] == 1]
  Zy = [z where B[z,y] == 1]
  for x in Xy:
    for z in Zy:
      if C[x,z] == 1:
        H.push([x,y,z])

PA = projectXY(H)
PB = projectZY(H)
PC = projectXZ(H)

metrics = {
  voxelCount: H.length,
  frontIoU: iou(PA,A),
  sideIoU: iou(PB,B),
  topIoU: iou(PC,C),
  missingFront: count(A - PA),
  missingSide: count(B - PB),
  missingTop: count(C - PC),
  extraFront: count(PA - A), // should be zero by construction
  extraSide: count(PB - B),
  extraTop: count(PC - C),
  isolatedFrontPixels: count((x,y) in A with no compatible z),
  isolatedSidePixels: count((z,y) in B with no compatible x),
  unsupportedTopPixels: count((x,z) in C with no compatible y)
}
```

### Soft slack sweep 의사코드

```js
for slackTopRadius of [0,1,2,4,8]:
  Csoft = dilate(C, slackTopRadius)
  H = visualHull(A,B,Csoft)
  metricsAgainstOriginalC = projectMetrics(H, A, B, C)
  metricsAgainstSoftC = projectMetrics(H, A, B, Csoft)
  slackCost = meanDistance(projectXZ(H), C)
```

### Metric

```text
voxelCount / sampledPointCount
front/right/top IoU
missing and extra pixels per view
unsupportedTopPixelRatio
isolatedFront/Side pixel ratio
row graph edge density per y
slack radius vs IoU curve
reveal density histogram
```

### 성공 기준

Exact mode:

```text
frontIoU >= 0.98
sideIoU >= 0.98
topIoU >= 0.98
extraFront=extraSide=extraTop=0
unsupportedTopPixelRatio <= 0.02
point budget can be sampled to browser-safe size
```

Soft/research mode:

```text
front/right degradation <= 2%
topIoU >= 0.90 preferred
slackCost reported explicitly
No production top view unless marked soft and QA-visible
```

### 실패 판정

```text
Any canonical view IoU < 0.90
front/right clean 2-view is degraded by top constraint
slack required so large that top image no longer recognizable
voxel count explodes beyond render budget without sampling strategy
```

---

## Experiment 3. Directional color shader QA

### 질문

점 하나가 view별로 다른 색을 보이도록 하되, texture swap/opacity gate 없이 directional material로 설명 가능한가?

### 입력

```text
point cloud from selected row policy
per-point front target color cF_i
per-point right target color cR_i
optional top target color cT_i if 3-view exact point set exists
view directions:
  front ωF=(0,0,1)
  right ωR=(1,0,0)
  top ωT=(0,1,0) or chosen convention
basis:
  two/three angular lobes
  spherical harmonics order 1/2
  learned small basis optional later
```

### Shader model pseudocode

```glsl
// Not production code yet. QA model only.
vec3 colorForDirection(vec3 viewDir, PointCoeffs coeff) {
  float f = pow(max(0.0, dot(viewDir, coeff.frontNormal)), sharpness);
  float r = pow(max(0.0, dot(viewDir, coeff.rightNormal)), sharpness);
  float t = pow(max(0.0, dot(viewDir, coeff.topNormal)), sharpness);
  float s = max(1e-4, f + r + t);
  return (f * coeff.frontColor + r * coeff.rightColor + t * coeff.topColor) / s;
}
```

### JS QA pseudocode

```js
for sharpness of [2,4,8,16]:
  for theta of sampleAngles(0, 90, step=5):
    colors = points.map(p => colorForDirection(direction(theta), p.coeff, sharpness))
    if theta is canonical:
      err = rmse(colors, targetColorsForThatView)
    smooth = meanNorm(colors(theta) - colors(theta-5deg))
    leakage = wrongLobeWeightAtCanonical(theta)
  write metrics
```

### Metric

```text
frontColorRMSE
rightColorRMSE
topColorRMSE if applicable
canonical wrong-lobe leakage
midAngleSmoothness mean/max
max per-frame color jump
alphaMinimum, alphaPolicy = must not be opacity gate
```

### 성공 기준

```text
front/right color RMSE improves >= 25% over fixed shared blend
canonical wrong-lobe leakage <= 5~10% depending sharpness
mid-angle max jump below visible pop threshold
all points remain rendered; no view-dependent alpha-to-zero
```

### 실패 판정

```text
Sharp lobes create abrupt pop
Soft lobes wash colors into current blend quality
Implementation requires view-specific texture swap or opacity gate
```

---

## Experiment 4. Angular morph feasibility

### 질문

시선 방향 `θ`에 따라 target image가 조금 변할 때, fixed geometry/material로 충분한가? 아니면 micro-displacement가 필요한가?

### 입력

```text
canonical front/right targets
synthetic intermediate target sets:
  A. color-only change
  B. local texture shift with same silhouette
  C. arm/limb silhouette shift by 2 px, 4 px, 8 px
point cloud from selected row policy
```

### Pseudocode: fixed color/material only

```js
for targetSequence of sequences:
  optimize/fill directional color coefficients only
  for theta in sequence:
    rendered = rasterizeFixedPointsWithDirectionalColor(P, theta)
    metric[theta] = compare(rendered, target[theta])
```

### Pseudocode: bounded micro-displacement

```js
for epsilonPx of [0,1,2,4,8]:
  for point i:
    p_i(theta) = p_i0 + sum_m d_im * basis_m(theta)
    constrain p_i(canonicalAngles) == p_i0
    constrain norm(project(d_i)) <= epsilonPx
  optimize d to improve intermediate targets
  measure canonical damage and intermediate gain
```

### Metric

```text
canonicalFrontIoUDrop
canonicalRightIoUDrop
intermediateIoUGain
maxProjectedDisplacement
meanProjectedDisplacement
temporalSmoothness = mean ||p_i(θ+Δ)-p_i(θ)||
pointsExceedingPhysicalBoundRatio
```

### 성공 기준

```text
For color-only/texture-only targets: geometry epsilon=0 should pass.
For silhouette arm shift:
  canonical IoU drop <= 1%
  intermediate IoU gain >= 0.05
  max displacement <= 2~4 px
If required displacement > 4 px, classify as geometry-needed and defer.
```

### 실패 판정

```text
canonical views no longer preserved
motion reads as view-dependent fake/gate
large silhouette motion impossible without adding/removing visible support
```

---

## Minimal implementation notes for future promotion

### Shared utilities to extract from `src/main.ts` later

현재 `src/main.ts` 안에 mask extraction과 cloud generation이 묶여 있다. 실험이 반복되면 production 변경 전에 다음 순서로만 분리하는 것이 안전하다.

```text
src/maskRows.ts      # draw/extract rows, no renderer side effect
src/rowMatching.ts   # min/max/OT policies
src/projectionQa.ts  # rasterize projections and IoU metrics
```

하지만 이번 탐색에서는 production 파일을 수정하지 않는다.

### Required QA fields if promoted

```text
rowMatchingPolicy
projectionCount
projectionOnlyPointCount
noProjectionOnlyPoints
frontProjectionIoU
rightProjectionIoU
topProjectionIoU if enabled
colorPolicy: fixedBlend | directionalBasis
viewDependentOpacityGate: false
viewDependentGeometry: false unless explicit research mode
```

---

## Acceptance summary for next week

1. Row OT accepted if it matches current 2-view legibility and improves color conflict/banding metrics.
2. Directional color accepted if it improves canonical color error without alpha/opacity gating.
3. 3-view accepted only if visual hull exact feasibility passes or soft mode is explicitly labeled research.
4. Angular silhouette morph is not accepted into production unless canonical damage is negligible and displacement remains physically small.
