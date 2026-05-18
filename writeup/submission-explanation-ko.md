# 제출 설명문: One Cloud, Multiple Readings

## 1. 구현 아이디어와 목적

이 작품은 하나의 3D 점구름이 관찰 방향에 따라 서로 다른 2D 이미지로 읽히는 렌티큘러형 3D 착시를 목표로 구현했다.
정면에서는 거위 이미지가 보이고, 오른쪽에서는 넙죽이 이미지가 보이도록, 두 이미지를 하나의 물리적 점 집합 안에 함께 배치했다.
핵심 목적은 “시점이 바뀌면 인식이 바뀌지만, 실제 3D 객체는 하나”라는 투영 기반 착시를 브라우저 WebGL 환경에서 직접 보여주는 것이다.

## 2. 핵심 원리

각 점은 하나의 3차원 좌표 `p=(x,y,z)`를 가진다.
정면 `+Z` 카메라는 이 점을 `(x,y)`로 읽고, 오른쪽 `+X` 카메라는 같은 점을 `(z,y)`로 읽는다.
따라서 한 점의 `x` 좌표는 거위 이미지의 가로 위치를, 같은 점의 `z` 좌표는 넙죽이 이미지의 가로 위치를 담당한다.
두 이미지가 같은 `y` 행을 공유하도록 맞추면, 한 점이 정면 이미지와 측면 이미지의 구성 요소를 동시에 담당할 수 있다.
이 원리를 근거로 2D 이미지 두 장을 하나의 3D 점구름으로 역투영했다.

## 3. 점구름 생성 방식

먼저 `artifacts/reference-image/goose.jpg`와 `artifacts/reference-image/nubzuki.jpg`를 Canvas 2D에 그려 픽셀 단위로 분석했다.
이미지 가장자리와 연결된 흰 배경을 분리하여 객체 내부의 흰 영역은 형태 정보로 유지했다.
각 이미지에서 활성 픽셀을 행(row) 단위로 모으고, 같은 행의 거위 픽셀과 넙죽이 픽셀을 짝지었다.
행 `r`에 대해 정면 이미지의 활성 x좌표 집합을 `X_r`, 측면 이미지의 활성 x좌표 집합을 `Z_r`로 두었다.
각 행에서는 `N_r=max(|X_r|, |Z_r|)`개의 점을 만들고, 더 짧은 쪽 좌표열은 반복 사용하여 두 이미지의 밀도를 함께 보존했다.
생성된 점은 다음 식으로 배치했다.

```text
p_i^r = (x_i, y_r, z_i)
Front +Z projection: (x_i, y_r) -> goose
Right +X projection: (z_i, y_r) -> nubzuki
```

이 방식으로 현재 결과는 18,102개의 점을 가진 하나의 `THREE.BufferGeometry`로 구성된다.

## 4. 색 표현 방식

각 점에는 위치뿐 아니라 하나의 고정 RGB 색상도 함께 저장했다.
거위 이미지에서 추출한 색과 넙죽이 이미지에서 추출한 색을 같은 행의 대응 픽셀 기준으로 섞어, 하나의 per-point color attribute로 기록했다.
색은 점 자체의 속성으로 저장되므로, 어느 방향에서 보아도 같은 물리적 점의 고정 색상을 관찰하게 된다.
이 구현을 통해 거위의 주황색/검은색 디테일과 넙죽이의 파란색/분홍색 계열이 하나의 점구름 안에서 함께 드러나도록 했다.

## 5. 렌더링과 뷰어

렌더링은 Vite + TypeScript + Three.js 기반 브라우저 WebGL로 구현했다.
장면의 핵심 객체는 하나의 `THREE.Points`이며, 이 객체는 하나의 `BufferGeometry`와 `position`, `color` attribute를 사용한다.
점은 `ShaderMaterial`로 둥근 point sprite와 약한 glow를 적용해, 픽셀 기반 이미지가 점구름으로 부드럽게 읽히도록 했다.
정면, 오른쪽, 뒤쪽, 왼쪽, 3D reveal, 자유 orbit 모드를 제공하여 착시 이미지와 실제 공간 구조를 모두 확인할 수 있게 했다.
정면 `+Z` 버튼은 거위 projection을, 오른쪽 `+X` 버튼은 넙죽이 projection을 보여준다.
뒤쪽과 왼쪽은 같은 점구름의 반대 방향 투영이므로 mirror view로 작동한다.

## 6. 10초 영상 연출

제출 영상은 단순 회전보다 착시 구조를 이해하기 쉬운 카메라 경로로 구성했다.
처음에는 `+X`에서 넙죽이를 크게 보여주고, 같은 위치에서 약한 zoom breathing으로 시작 프레임을 안정화한다.
그 다음 `+X`에서 `-Z` 방향으로 quarter-arc 회전을 수행하여 같은 점들이 다른 이미지로 재배열되는 과정을 보여준다.
`-Z`에서는 mirrored goose를 잠시 유지하여 두 번째 projection을 인식할 시간을 준다.
마지막에는 `-Z` 방향에서 위와 뒤로 부드럽게 crane-out한 뒤, 45도 overhead 방향으로 drift하며 전체 3D 점구름 구조를 공개한다.
이 경로는 “두 이미지 전환”과 “하나의 3D 구조 공개”를 시간적으로 분리하기 위해 설계했다.

## 7. 구현 결과

현재 브라우저 뷰어는 18,102개의 공유 점으로 거위와 넙죽이 두 이미지를 표현한다.
정면 projection은 거위 실루엣과 색을 보여주고, 오른쪽 projection은 같은 점들의 `z,y` 좌표를 통해 넙죽이 실루엣과 색을 보여준다.
3D reveal에서는 한 공간에 흩어진 점들의 서로 다른 투영 결과가 두 이미지로 읽히는 구조를 확인할 수 있다.
녹화 기능은 10초 WebM을 생성하며, 필요하면 ffmpeg로 MP4 제출 형식으로 변환할 수 있다.

## 8. 검증

프로젝트에는 `window.__LENTICULAR_QA__`와 `scripts/shared-space-harness.mjs`를 통해 핵심 구조를 검증하는 장치를 넣었다.
검증 항목은 scene의 `THREE.Points` 개수, 공유 `BufferGeometry` 사용 여부, `position/color` attribute 수, projection 수, 점 개수, row matching 통계, 색상 정책을 포함한다.
최근 main 기준 검증에서 `npm run harness`, `npm run build`, `npm run qa:submission`이 통과했다.
최종 QA 리포트는 `artifacts/final-qa-20260518T042540Z.json`에 저장했다.

## 9. 재현 방법

```bash
npm install
npm run dev
# open http://127.0.0.1:5173
npm run harness
npm run qa:submission
```

브라우저에서 `Front +Z: goose`, `Right +X: nubzuki`, `3D reveal`, `10초 WebM 녹화` 버튼으로 결과를 확인할 수 있다.
