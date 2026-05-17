# 프로젝트 명세서

공식 contest 기준으로 이 프로젝트는 **handcrafted / procedurally generated 3D scene**에 해당합니다. 과제는 3D object/scene을 reconstruct, generate, 또는 design/handcraft한 뒤 가장 인상적인 rendering video로 보여주는 것이고, Technology Score는 scene 생성과 렌더링 과정의 technical novelty/difficulty, Creativity Score는 originality/artistic value를 봅니다. 또한 Blender rendering, commercial software, 외부 3D asset, closed-source tool은 금지이고, webpage + `.js` 같은 3D content 제출이 허용됩니다. ([KAIST 3DML](https://3dml.kaist.ac.kr/3d-rendering-contest/?utm_source=chatgpt.com))

---

# 1. 프로젝트 개요

## Project Title

**What We See Is Not What Exists: A Perceptual Twin Room**

## One-line Concept

기준 카메라에서는 정상적인 방과 문장처럼 보이지만, 카메라가 움직이면 실제 3D geometry가 왜곡되어 있음을 드러내는 **projective illusion rendering**.

## 핵심 아이디어

이 프로젝트는 착시 이미지를 2D로 그리는 것이 아니라, **기준 카메라의 projection constraint를 만족하도록 3D geometry를 생성**합니다.

일반적인 렌더링은:

[

3D\ geometry \rightarrow camera\ projection \rightarrow 2D\ image

]

이 프로젝트는 반대로:

[

desired\ 2D\ percept \rightarrow back\ projection \rightarrow distorted\ 3D\ geometry

]

로 구현합니다.

즉, 사람이 보는 **perceived world**와 실제 존재하는 **physical world**가 다르다는 것을 3D rendering으로 보여주는 작품입니다.

---

# 2. 제출 결과물 명세

공식 제출 조건에 맞춰 아래 결과물을 준비합니다. 대표 이미지, 10초 이하 mp4, 하나의 3D content, source code/data, write-up이 필요하고, video / 3D content / code-data / write-up 중 하나라도 누락되면 zero score가 될 수 있습니다. ([KAIST 3DML](https://3dml.kaist.ac.kr/3d-rendering-contest/?utm_source=chatgpt.com))

| 제출물 | 명세 |
| --- | --- |
| Representative image | `representative.png`, 1920×1080 이하, 5MB 이하 |
| Rendering video | `output.mp4`, 10초 이하, 1920×1080 이하, 50MB 이하 |
| 3D content | `index.html` + `src/*.js` + generated scene data |
| Source code/data | scene generator, renderer, config, reproducibility files |
| Write-up | 4 pages 이하, title / teammates / description / technical aspects / reproduction steps / references |

---

# 3. 최종 영상 구성

## 10초 영상 시나리오

| 시간 | 장면 | 목적 |
| --- | --- | --- |
| 0–2s | 흩어진 3D 조각들 사이를 카메라가 이동 | 처음에는 의미 없는 geometry처럼 보이게 함 |
| 2–3.5s | 특정 위치에 도달하면 조각들이 **“WHAT WE SEE”** 로 정렬 | 첫 번째 착시 hook |
| 3.5–5s | 글자 뒤에 정상적인 방처럼 보이는 공간 등장 | perceived room 제시 |
| 5–7s | 카메라가 옆으로 이동하며 방이 찌그러진 실제 geometry임을 reveal | physical geometry reveal |
| 7–9s | wireframe, camera rays, reference camera frustum 표시 | 기술적 원리 시각화 |
| 9–10s | **“≠ WHAT EXISTS”** / **“Perception is prediction.”** | 메시지 마무리 |

## 최종 메시지

> **WHAT WE SEE ≠ WHAT EXISTS**
> 

다른 과목의 Brain Digital Twin 발표와 연결하면:

> 좋은 visual brain digital twin은 물리적 geometry만 예측하는 것이 아니라, 인간이 실제로 어떻게 지각하는지도 예측해야 한다.
> 

---

# 4. 기술 명세

## 4.1 핵심 기술

| 기술 요소 | 구현 내용 | 점수 기여 |
| --- | --- | --- |
| Camera model | reference camera와 render camera 분리 | 수업 개념 연결 |
| Inverse projection | 2D target point를 3D ray로 back-project | 핵심 기술 |
| Procedural mesh generation | distorted room mesh 자동 생성 | 손모델링이 아닌 알고리즘적 생성 |
| Anamorphic text | 2D text mask를 3D 조각으로 변환 | 창의성 + 기술성 |
| Rasterization rendering | WebGL/Three.js 기반 custom rendering | Blender rendering 회피 |
| Camera animation | 기준 시점 → reveal 시점 전환 | 영상 narrative |
| Technical overlay | rays, wireframe, ghost room 표시 | 평가자가 기술을 즉시 이해 |

수업 자료에서 camera model은 world coordinate의 3D point (X)를 image coordinate (x)로 보내는 식 (x = K[R|t]X = PX)로 설명되고, (x)와 (X)는 homogeneous coordinates로 표현됩니다. 이 프로젝트는 이 projection 관계를 거꾸로 사용합니다.

---

# 5. Scene 구성 명세

하나의 3D scene 안에 아래 object들을 모두 포함합니다.

| Object | 설명 | 생성 방식 |
| --- | --- | --- |
| Anamorphic text pieces | 특정 시점에서만 “WHAT WE SEE”로 보이는 조각들 | 2D text mask sampling → ray back-projection |
| Distorted room | 기준 시점에서 정상적인 방처럼 보이는 찌그러진 mesh | 2D room layout corners → depth assignment → mesh |
| Same-size spheres | 같은 물리 크기지만 다르게 지각되는 두 구 | 같은 radius, 다른 depth |
| Grid/checker surfaces | 방의 perspective cue 강화 | procedural material |
| Reference camera frustum | 착시가 성립하는 기준 카메라 표시 | line geometry |
| Camera rays | 2D point가 3D ray 위에 놓였음을 시각화 | line geometry |
| Ghost perceived room | 사람이 지각한 정상 방을 반투명 overlay로 표시 | transparent box/lines |
| Ending text | “≠ WHAT EXISTS” | screen overlay 또는 3D text pieces |

Polygon mesh는 vertices, edges, faces로 polyhedral object를 정의하는 representation이고, graphics에서 많이 쓰이며 rendering에 적합하다는 점이 수업 자료와도 맞습니다.

---

# 6. 수학적 구현 명세

## 6.1 Reference Camera

기준 카메라를 하나 고정합니다.

```
Reference camera:
  position: (0, 0, 8)
  target:   (0, 0, 0)
  fov:      50 degrees
  aspect:   16 / 9
  near/far: 0.1 / 100
```

이 reference camera에서만 다음이 성립해야 합니다.

1. 흩어진 조각들이 “WHAT WE SEE”로 보임.
2. distorted room이 정상적인 방처럼 보임.
3. 같은 크기 sphere들이 서로 다른 크기로 지각됨.

## 6.2 Back-projection

2D point (\tilde{x}_i = (u_i, v_i, 1))를 기준 카메라의 ray로 변환합니다.

[

\mathbf{d}_i = R^\top K^{-1}\tilde{\mathbf{x}}_i

]

[

\mathbf{X}_i = \mathbf{C} + \lambda_i \mathbf{d}_i

]

| 기호 | 의미 |
| --- | --- |
| (K) | camera intrinsic matrix |
| (R) | reference camera rotation |
| (C) | reference camera center |
| (\tilde{x}_i) | 기준 화면의 2D point |
| (\lambda_i) | 선택한 depth |
| (X_i) | 실제 3D point |

Three.js에서는 `Vector3.unproject(camera)`를 이용해 구현합니다.

```jsx
function backprojectNDC(camera, u, v, depth) {
  const nearPoint = new THREE.Vector3(u, v, -1).unproject(camera);
  const farPoint  = new THREE.Vector3(u, v,  1).unproject(camera);

  const dir = farPoint.sub(nearPoint).normalize();
  const C = camera.position.clone();

  return C.add(dir.multiplyScalar(depth));
}
```

## 6.3 Reprojection Test

기술성을 명확히 보여주기 위해 generator 내부에서 reprojection error를 계산합니다.

```
For each generated 3D point X_i:
  project X_i back to reference camera
  compare projected point with target 2D point x_i
  report mean reprojection error
```

Acceptance criterion:

```
mean reprojection error < 1 pixel
```

이 값을 write-up에 넣으면 “착시가 우연히 된 것”이 아니라 projection constraint를 만족한다는 점이 드러납니다.

---

# 7. Anamorphic Text 구현 명세

## 목표

기준 카메라에서만:

```
WHAT WE SEE
```

라는 문장이 보이게 합니다.

## 입력

```json
{
  "text": "WHAT WE SEE",
  "canvasWidth": 1024,
  "canvasHeight": 256,
  "sampleStride": 8,
  "depthRange": [3.0, 7.0],
  "piecePixelSize": 6
}
```

## 알고리즘

1. HTML Canvas 2D에 `"WHAT WE SEE"`를 그림.
2. alpha 또는 luminance가 threshold 이상인 pixel을 sampling.
3. pixel 좌표를 NDC 좌표 ([-1, 1])로 변환.
4. 각 NDC point를 reference camera ray로 back-project.
5. 각 ray에 seeded random depth를 부여.
6. 그 위치에 작은 square plane을 배치.
7. plane은 reference camera를 바라보도록 orient.
8. plane size는 depth에 비례시켜 reference view에서 일정한 pixel size가 되도록 함.

## Pseudocode

```jsx
function generateAnamorphicText(text, refCamera, config) {
  const maskPoints = sampleTextMask(text, config);

  const meshes = [];
  for (const p of maskPoints) {
    const [u, v] = pixelToNDC(p.x, p.y, config.canvasWidth, config.canvasHeight);

    const depth = seededRandom(config.depthMin, config.depthMax);
    const position = backprojectNDC(refCamera, u, v, depth);

    const size = screenConstantWorldSize(refCamera, u, v, depth, config.piecePixelSize);
    const piece = createTextPiece(position, size, refCamera);

    meshes.push(piece);
  }

  return meshes;
}
```

## 구현 팁

많은 조각을 만들 경우 성능을 위해 `InstancedMesh`를 사용합니다.

```
Recommended:
  500–2000 pieces
```

너무 많으면 영상이 복잡해지고, 너무 적으면 글자가 안 읽힙니다.

---

# 8. Perceptual Twin Room 구현 명세

## 목표

기준 카메라에서는 정상적인 직육면체 방처럼 보이지만, 실제로는 찌그러진 mesh를 생성합니다.

## 8.1 2D room layout

기준 화면에서 보일 방의 2D layout을 먼저 정의합니다.

```jsx
const points2D = {
  outerTL: [-0.85,  0.65],
  outerTR: [ 0.85,  0.65],
  outerBR: [ 0.85, -0.65],
  outerBL: [-0.85, -0.65],

  innerTL: [-0.35,  0.25],
  innerTR: [ 0.35,  0.25],
  innerBR: [ 0.35, -0.25],
  innerBL: [-0.35, -0.25]
};
```

이 2D layout은 기준 카메라에서 관객이 보게 될 **perceived room**입니다.

## 8.2 비대칭 depth assignment

정상적인 방이라면 좌우 depth가 대칭이어야 하지만, 여기서는 일부러 비대칭 depth를 줍니다.

```jsx
const depths = {
  outerTL: 3.0,
  outerTR: 5.2,
  outerBR: 5.8,
  outerBL: 3.4,

  innerTL: 7.2,
  innerTR: 11.0,
  innerBR: 10.6,
  innerBL: 7.8
};
```

이 값들이 illusion strength를 결정합니다.

```
illusionStrength = 0.0 → 거의 정상 방
illusionStrength = 1.0 → 강한 왜곡
```

## 8.3 3D vertices 생성

```jsx
const V = {};

for (const key in points2D) {
  const [u, v] = points2D[key];
  V[key] = backprojectNDC(refCamera, u, v, depths[key]);
}
```

## 8.4 room mesh 생성

각 wall은 quad이고, WebGL rendering을 위해 triangle 2개로 나눕니다.

```jsx
function makeQuad(a, b, c, d, material) {
  const vertices = new Float32Array([
    a.x, a.y, a.z,
    b.x, b.y, b.z,
    c.x, c.y, c.z,

    a.x, a.y, a.z,
    c.x, c.y, c.z,
    d.x, d.y, d.z
  ]);

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(vertices, 3));
  geometry.computeVertexNormals();

  return new THREE.Mesh(geometry, material);
}
```

방 구성:

```jsx
const leftWall = makeQuad(
  V.outerTL, V.innerTL, V.innerBL, V.outerBL, wallMat
);

const rightWall = makeQuad(
  V.innerTR, V.outerTR, V.outerBR, V.innerBR, wallMat
);

const ceiling = makeQuad(
  V.outerTL, V.outerTR, V.innerTR, V.innerTL, ceilingMat
);

const floor = makeQuad(
  V.innerBL, V.innerBR, V.outerBR, V.outerBL, floorMat
);

const backWall = makeQuad(
  V.innerTL, V.innerTR, V.innerBR, V.innerBL, backWallMat
);
```

## 8.5 Grid / checker material

외부 texture를 쓰지 않고 procedural checker shader를 사용합니다.

```
No external texture asset.
No external 3D asset.
All visual patterns generated from shader or UV coordinates.
```

렌더링 방식은 WebGL rasterization입니다. 수업 자료에서 rasterization은 각 mesh face를 2D screen에 project하고, projected face 내부 pixel에 vertex data를 보간하며, depth가 가까운 pixel만 write하는 object-centric rendering 방식으로 설명됩니다.

---

# 9. Same-size Object Illusion 명세

## 목표

두 개의 sphere가 같은 physical radius를 가지지만, 기준 시점에서는 크기가 다르게 보이게 합니다.

```jsx
const radius = 0.35;

const sphereA = createSphere(radius);
const sphereB = createSphere(radius);

sphereA.position.copy(backprojectNDC(refCamera, -0.45, -0.25, 4.0));
sphereB.position.copy(backprojectNDC(refCamera,  0.45, -0.25, 8.0));
```

## 영상에서 보여줄 label

```
same physical size
different perceived size
```

## 역할

이 요소는 관객이 착시를 더 직관적으로 이해하도록 돕습니다. 방만 찌그러져 있으면 “왜 착시인지”가 늦게 전달될 수 있지만, 같은 크기의 sphere 두 개가 다르게 보이면 메시지가 즉시 전달됩니다.

---

# 10. Camera Animation 명세

## 두 개의 카메라 개념

| 카메라 | 역할 |
| --- | --- |
| Reference Camera | 착시가 성립하는 기준 시점 |
| Render Camera | 최종 영상에서 움직이는 카메라 |

초기에는 render camera가 reference camera 근처로 이동하고, 이후 옆으로 이동하며 착시를 깨뜨립니다.

## Keyframes

```jsx
const keyframes = [
  {
    time: 0.0,
    position: [-2.5, 0.8, 8.5],
    target: [0, 0, 0],
    phase: "approach_text"
  },
  {
    time: 0.25,
    position: [0, 0, 8],
    target: [0, 0, 0],
    phase: "text_aligned"
  },
  {
    time: 0.45,
    position: [0, 0, 8],
    target: [0, 0, 0],
    phase: "room_perceived"
  },
  {
    time: 0.70,
    position: [4.0, 2.0, 7.0],
    target: [0, 0, 0],
    phase: "reveal_physical"
  },
  {
    time: 0.90,
    position: [6.5, 3.0, 9.0],
    target: [0, 0, 0],
    phase: "technical_overlay"
  },
  {
    time: 1.00,
    position: [6.5, 3.0, 9.0],
    target: [0, 0, 0],
    phase: "ending"
  }
];
```

## Rotation interpolation

카메라 회전은 Euler angle로 직접 보간하지 말고 quaternion 기반 보간을 쓰는 것이 좋습니다. 수업에서도 3D rotation은 비가환적이고, unit quaternion이 3D rotation matrix를 표현할 수 있음을 다룹니다.

Three.js에서는:

```jsx
camera.quaternion.slerpQuaternions(q0, q1, alpha);
```

을 사용할 수 있습니다.

---

# 11. Technical Overlay 명세

후반부 7–9초에 기술적 원리를 보여줍니다.

## 표시할 요소

| Overlay | 설명 |
| --- | --- |
| Wireframe physical room | 실제 왜곡 geometry |
| Reference camera frustum | 착시가 성립하는 카메라 |
| Back-projection rays | 2D point가 3D ray 위에 있음을 표시 |
| Ghost perceived room | 사람이 지각한 정상 방 |
| Reprojection error text | mean reprojection error 표시 |

## Camera ray 생성

```jsx
function makeRayLine(camera, u, v, depth, material) {
  const start = camera.position.clone();
  const end = backprojectNDC(camera, u, v, depth);
  const geometry = new THREE.BufferGeometry().setFromPoints([start, end]);
  return new THREE.Line(geometry, material);
}
```

추천 개수:

```
Room corners: 8 rays
Text sample: 8–12 rays
Total: 16–20 rays
```

너무 많이 그리면 화면이 복잡해지므로 일부만 표시합니다.

---

# 12. Software Architecture

## 추천 기술 스택

| 항목 | 선택 |
| --- | --- |
| Renderer | Three.js / WebGL |
| Scene generation | JavaScript |
| Video export | browser capture 또는 PNG frames + ffmpeg |
| 3D content format | webpage + `.js` files |
| Geometry | procedural mesh, planes, spheres, lines |
| Texture | procedural checker/grid |
| External 3D assets | 사용하지 않음 |
| Blender rendering | 사용하지 않음 |

## 폴더 구조

```
perceptual_twin_room/
  index.html
  package.json
  README.md
  scene_config.json

  src/
    main.js
    camera.js
    inverse_projection.js
    generate_text.js
    generate_room.js
    generate_objects.js
    overlays.js
    animation.js
    materials.js
    capture.js
    utils.js

  output/
    representative.png
    output.mp4

  writeup/
    writeup.pdf
```

## 모듈별 역할

| 파일 | 역할 |
| --- | --- |
| `main.js` | renderer, scene, camera, animation loop 초기화 |
| `camera.js` | reference camera / render camera 생성 |
| `inverse_projection.js` | backproject, project, reprojection error 계산 |
| `generate_text.js` | anamorphic text 생성 |
| `generate_room.js` | distorted room mesh 생성 |
| `generate_objects.js` | spheres, ghost room 등 생성 |
| `overlays.js` | rays, frustum, wireframe, labels |
| `animation.js` | 10초 timeline과 camera path |
| `materials.js` | procedural checker/grid/wireframe material |
| `capture.js` | frame export 또는 MediaRecorder |
| `scene_config.json` | 모든 parameter 저장 |

---

# 13. `scene_config.json` 예시

```json
{
  "projectTitle": "What We See Is Not What Exists",

  "render": {
    "width": 1920,
    "height": 1080,
    "durationSec": 10,
    "fps": 60
  },

  "referenceCamera": {
    "position": [0, 0, 8],
    "target": [0, 0, 0],
    "fov": 50,
    "near": 0.1,
    "far": 100
  },

  "anamorphicText": {
    "text": "WHAT WE SEE",
    "canvasWidth": 1024,
    "canvasHeight": 256,
    "sampleStride": 8,
    "depthMin": 3.0,
    "depthMax": 7.0,
    "piecePixelSize": 6,
    "seed": 479
  },

  "room": {
    "outerTL": [-0.85, 0.65],
    "outerTR": [0.85, 0.65],
    "outerBR": [0.85, -0.65],
    "outerBL": [-0.85, -0.65],
    "innerTL": [-0.35, 0.25],
    "innerTR": [0.35, 0.25],
    "innerBR": [0.35, -0.25],
    "innerBL": [-0.35, -0.25],

    "depths": {
      "outerTL": 3.0,
      "outerTR": 5.2,
      "outerBR": 5.8,
      "outerBL": 3.4,
      "innerTL": 7.2,
      "innerTR": 11.0,
      "innerBR": 10.6,
      "innerBL": 7.8
    }
  },

  "objects": {
    "sphereRadius": 0.35,
    "sphereA": { "ndc": [-0.45, -0.25], "depth": 4.0 },
    "sphereB": { "ndc": [0.45, -0.25], "depth": 8.0 }
  }
}
```

모든 randomness는 seed로 고정합니다. 그래야 source code/data로 결과가 재현됩니다.

---

# 14. 구현 일정

## Phase 1 — 핵심 inverse projection 구현

목표:

```
project(backproject(u, v, depth)) ≈ (u, v)
```

작업:

1. Three.js scene 초기화
2. reference camera 생성
3. `backprojectNDC()` 구현
4. `projectToNDC()` 구현
5. reprojection error test 작성

완료 기준:

```
mean reprojection error < 1 pixel
```

---

## Phase 2 — Anamorphic Text 구현

목표:

```
기준 카메라에서 “WHAT WE SEE”가 읽힘.
카메라가 옆으로 가면 조각들이 흩어져 보임.
```

작업:

1. Canvas text mask 생성
2. pixel sampling
3. NDC 변환
4. ray back-projection
5. text pieces 생성
6. InstancedMesh 최적화

완료 기준:

```
reference view에서 문장이 명확히 읽힘
reveal view에서 문장이 깨짐
```

---

## Phase 3 — Perceptual Room 구현

목표:

```
기준 카메라에서 정상적인 방처럼 보임.
옆 시점에서 찌그러진 physical geometry가 드러남.
```

작업:

1. 2D room layout 정의
2. 각 corner depth 설정
3. distorted vertices 생성
4. wall / floor / ceiling mesh 생성
5. procedural grid/checker material 적용

완료 기준:

```
reference view에서는 rectangular room처럼 보임
side view에서는 비대칭 distorted room이 명확히 보임
```

---

## Phase 4 — Narrative 요소 추가

목표:

```
착시가 단순 수학 데모가 아니라 작품처럼 보이게 함.
```

작업:

1. same-size sphere 2개 배치
2. “same physical size / different perceived size” label
3. ghost perceived room 추가
4. ending text “≠ WHAT EXISTS” 추가
5. lighting / color transition 추가

완료 기준:

```
무음으로 봐도 메시지가 이해됨
```

---

## Phase 5 — Technical Overlay 구현

목표:

```
평가자가 기술적 원리를 영상 안에서 바로 이해하게 함.
```

작업:

1. wireframe toggle
2. reference camera frustum
3. back-projection rays
4. reprojection error overlay
5. labels: Reference Camera / Physical Twin / Perceptual Twin

완료 기준:

```
7–9초 구간에서 inverse projection 원리가 시각적으로 드러남
```

---

## Phase 6 — 제출물 정리

작업:

1. `output.mp4` export
2. `representative.png` 캡처
3. source code 정리
4. `README.md` 작성
5. write-up 작성
6. references 정리
7. file size / duration / resolution 확인

완료 기준:

```
mp4 ≤ 10 sec
mp4 ≤ 50MB
resolution ≤ 1920×1080
3D content ≤ 100MB
all files reproducible
```

---

# 15. MVP와 확장 기능

## MVP: 반드시 구현

이 5개만 제대로 해도 제출작으로 충분합니다.

```
1. Reference camera
2. Anamorphic “WHAT WE SEE”
3. Distorted room mesh
4. Camera reveal animation
5. Wireframe + rays
```

## Strong Version: 점수 강화

시간이 있으면 추가합니다.

```
1. Same-size sphere illusion
2. Ghost perceived room overlay
3. Reprojection error display
4. Procedural checker shader
5. Smooth quaternion camera interpolation
```

## Optional Bonus

시간이 정말 남으면 추가합니다.

```
1. Shadow illusion
2. “BRAIN” or “EYE” shadow projection
3. More advanced post-processing
```

하지만 shadow illusion은 필수로 넣지 않는 게 좋습니다. 10초 안에 너무 많은 착시를 보여주면 산만해질 수 있습니다.

---

# 16. 평가 전략

## Technology Score를 위한 주장

write-up에서 이렇게 강조합니다.

> We define a reference camera and generate 3D primitives by back-projecting target 2D perceptual points into 3D rays with different depth values. Under the reference camera, the scene forms readable text and a normal-looking room, while other viewpoints reveal the distorted physical geometry.
> 

기술 키워드:

```
camera matrix
homogeneous coordinates
inverse projection
depth ambiguity
anamorphic geometry
procedural mesh generation
WebGL rasterization
camera path rendering
wireframe reveal
reprojection error
```

## Creativity Score를 위한 주장

창의성은 아래 메시지에서 나옵니다.

> The project visualizes the difference between physical geometry and perceived 3D structure. It connects 3D rendering with visual perception: perception is not a direct copy of the world, but an interpretation of projected visual input.
> 

영상 문구:

```
WHAT WE SEE
≠
WHAT EXISTS
```

---

# 17. 리스크와 대응

| 리스크 | 원인 | 대응 |
| --- | --- | --- |
| 글자가 잘 안 읽힘 | text pieces가 너무 적거나 깊이 차가 너무 큼 | sampling stride 줄이기, depth range 축소 |
| 방이 정면에서도 이상해 보임 | depth asymmetry가 너무 강함 | illusionStrength 낮추기 |
| reveal이 약함 | depth 차이가 너무 작음 | 오른쪽 벽 / 뒤쪽 벽 depth 차이 키우기 |
| 화면이 복잡함 | rays, labels, text pieces가 너무 많음 | overlay는 후반 2초만 표시 |
| 성능 저하 | text piece mesh가 너무 많음 | InstancedMesh 사용 |
| 규칙 위반 위험 | 외부 asset 사용 | 모든 geometry와 texture procedural 생성 |
| 기술성이 약해 보임 | 착시 연출만 보임 | reprojection error, rays, wireframe, generator 설명 추가 |

---

# 18. Write-up 구조

## 1. Project Title

**What We See Is Not What Exists: A Perceptual Twin Room**

## 2. Brief Description

```
This project creates a distorted 3D room and anamorphic text that appear normal only from a reference camera. As the camera moves away, the physical geometry is revealed to be different from the perceived structure.
```

## 3. Technical Aspects

포함할 내용:

1. Reference camera definition
2. Camera model (x = K[R|t]X)
3. Inverse projection
4. Anamorphic text generation
5. Distorted room mesh generation
6. WebGL rasterization
7. Reprojection error
8. No external 3D assets / no Blender rendering

## 4. Reproduction Steps

예시:

```bash
npm install
npm run dev
```

또는:

```bash
python3 -m http.server 8000
```

실행 후:

```
Open http://localhost:8000
Press P to play the 10-second camera path.
Press W to toggle wireframe.
Press R to toggle camera rays.
```

## 5. References

반드시 적을 것:

```
- Three.js / WebGL library
- Any npm packages used
- Any font or non-3D asset if used
- Course lecture references
- Any copied/adapted code
```

기존 code, model, asset을 cite하지 않으면 zero score가 될 수 있으므로 write-up references는 매우 중요합니다. ([KAIST 3DML](https://3dml.kaist.ac.kr/3d-rendering-contest/?utm_source=chatgpt.com))

---

# 19. 최종 명세 요약

## Final Project Specification

```
Project:
  What We See Is Not What Exists: A Perceptual Twin Room

Type:
  Procedurally generated / handcrafted 3D scene

Renderer:
  WebGL / Three.js
  No Blender rendering

Core algorithm:
  1. Define a reference camera.
  2. Define target 2D percepts:
       - readable text
       - normal-looking room
  3. Back-project target 2D points into 3D rays.
  4. Assign different depths to create distorted physical geometry.
  5. Render from the reference camera to show the perceived scene.
  6. Move camera away to reveal the physical geometry.
  7. Show wireframe, rays, and labels.

Main visual elements:
  - “WHAT WE SEE” anamorphic text
  - distorted perceptual room
  - same-size sphere illusion
  - physical/perceptual twin overlay
  - “≠ WHAT EXISTS” ending

Expected scoring:
  Technology: 4–5
  Creativity: 5
  Risk: low to medium
```

---

# 20. 가장 중요한 구현 원칙

이 프로젝트는 **착시를 예쁘게 렌더링하는 것**이 아니라, 다음을 보여주는 프로젝트로 만들어야 합니다.

> **A 3D scene generated from camera projection constraints.**
> 

그래서 최종 제출물에서 반드시 보여야 하는 것은 세 가지입니다.

1. **기준 시점에서는 정상적으로 보인다.**
2. **카메라가 움직이면 실제 geometry가 왜곡되어 있음이 드러난다.**
3. **wireframe/rays/reprojection explanation으로 이것이 inverse projection 기반임을 보여준다.**

이 세 가지가 들어가면, 이 프로젝트는 3D rendering contest에 충분히 맞고, 기술성과 창의성을 모두 가져갈 수 있습니다.