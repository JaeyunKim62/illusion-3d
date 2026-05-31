# Shadow-Painter (스테인드글라스 그림자 아트 생성기)

**Shadow-Painter**는 입력 이미지를 스테인드글라스 형태의 3D 조각들로 분할하고, 3D 가상 공간에서 광원을 비추었을 때 벽면에 원본 형상의 그림자 예술(Shadow Art)이 맺히도록 설계된 시뮬레이터 겸 도구입니다.

이 프로그램은 PySide6 및 Qt 3D 그래픽 엔진을 사용하여 백프로젝션(Back-projection) 연산을 실시간으로 수행합니다.

---

## 주요 기능 (Key Features)

1. **이미지 세그멘테이션 (Image Segmentation)**
   - 일반 이미지 파일을 로드하여 CIELAB 색상 공간과 5차원 K-Means 클러스터링을 적용해 스테인드글라스 조각(보로노이 다이어그램 형태)으로 분할합니다.
   - **Pieces Count(조각 수)** 및 **Detail Sensitivity(상세도 민감도)** 슬라이더를 조작해 분할 패턴을 즉각적으로 조절할 수 있습니다.
   - 두 가지 마스크 모드를 지원합니다:
     - **Silhouette (Auto-mask)**: 피사체의 실루엣 영역만 분할합니다.
     - **Full Image Canvas**: 이미지의 캔버스 전체를 조각냅니다.

2. **3D 가상 공간 시뮬레이션 (3D Simulation Viewport)**
   - 분할된 2D 셀을 3D 입체 프리즘 메쉬(Glass Prism Mesh)로 돌출시키고 가상 3D 갤러리에 배치합니다.
   - 카메라 뷰 앵글을 구형 조작 기즈모(Angle Gizmo Widget) 혹은 3D 뷰포트 마우스 드래그(Orbit Control)로 제어할 수 있습니다.
   - **Spotlight** 및 **Colored Shadow** 렌더링을 켜거나 끌 수 있으며, 광원으로부터 나오는 투사선(Light Rays)을 시각화할 수 있습니다.

3. **실시간 광원 제어 (Real-time Light Source Control)**
   - 새로 추가된 **Light Position Control** 슬라이더를 사용해 광원을 벽면 중심 기준 좌우(X축)로 자유롭게 이동시킬 수 있습니다.
   - 광원의 이동에 맞춰 3D 공간의 그림자가 실시간으로 찌그러지고 이동하는 정밀한 실시간 투영 시뮬레이션을 제공합니다.

4. **다양한 내보내기 지원 (Export Options)**
   - **Export OBJ**: 생성된 3D 스테인드글라스 메쉬를 Wavefront OBJ 파일로 내보냅니다.
   - **Export SVG**: 제작용 2D 도안을 벡터 형식(SVG)으로 내보냅니다.

---

## 설치 및 환경 구축 (Setup & Installation)

이 프로젝트는 Python 3.10+ 환경과 다음 라이브러리를 사용합니다.

```bash
# 의존성 패키지 설치
pip install -r requirements.txt
```

### 주요 패키지 버전
- **PySide6**: `6.8.3` (GUI 및 Qt 3D 렌더링)
- **numpy**: `2.4.6` (3D 공간 수학 계산 및 데이터 연산)
- **opencv-python**: `4.13.0.92` (이미지 프로세싱 및 K-Means 세그멘테이션)
- **scipy**: `1.17.1` (기하 공간 계산 보조)

---

## 실행 방법 (How to Run)

패키지 형태로 실행해야 모듈 참조 오류(ModuleNotFoundError) 없이 정상 작동합니다.

```bash
# 프로젝트 루트 디렉토리(Shadow-Painter/)에서 아래 명령 실행
python -m shadow_painter.main
```

---

## UI 컨트롤 가이드 (UI Controls Guide)

- **Image Processing**:
  - `Load Image File`: 임의의 PNG, JPG 이미지를 불러옵니다.
  - `Pieces Count`: 스테인드글라스 조각 개수를 조절합니다 (20 ~ 500개).
  - `Detail Sensitivity`: 색상 정보를 얼마나 강하게 반영하여 조각 윤곽선을 생성할지 설정합니다.
- **Light Position Control**:
  - `Horizontal Position (X)`: 광원의 가로 위치를 조정합니다. 좌우 이동에 맞춰 그림자가 실시간으로 뒤틀리며 이동합니다.
- **Camera View Control**:
  - `Angle Gizmo`: 3D 구체 안의 조절점을 드래그하여 카메라 위치(Yaw, Pitch)를 변경합니다.
  - Checkboxes: 조명 활성화, 그림자 투영 활성화, 프로젝션 가이드라인(Rays) 표시 여부를 토글합니다.
- **System Controls**:
  - `Randomize Glass Depths`: 각 유리 조각의 Z축 깊이를 무작위로 재조정하여 다채로운 입체 구조를 만듭니다.
  - `Reset View Angle`: 카메라 앵글 및 광원 위치를 원래 정중앙 상태로 초기화합니다.
  - `Export OBJ / SVG`: 시뮬레이션한 결과물을 3D 및 2D 파일로 저장합니다.
