사용자는 한국어로 최종 보고를 원한다. 이전 답변은 너무 얕다고 지적했다. 이번에는 1시간 동안 실제 탐색/검증 중심으로 깊게 사고하고, 최종 알고리즘 몇 개를 제안하라.

작업 디렉터리: C:\00_Codes\illusion-3d
현재 브랜치 기대값: algorithm-exploration-20260518

중요: 최종 결과를 반드시 파일로 저장하라:
- artifacts/algorithm-exploration/deep-algorithm-proposal-20260518.md
가능하면 검증/실험용 스크립트 초안 또는 의사코드도 함께 저장하라:
- artifacts/algorithm-exploration/verification-plan-20260518.md
코드베이스의 production 파일(src/main.ts 등)은 수정하지 말라. artifacts/.hermes 아래 연구 노트만 작성 가능.

먼저 확인:
1. git branch/status 확인. 브랜치가 다르면 보고만 하고 강제 checkout하지 말 것.
2. README.md, CURRENT_HANDOFF.md, src/main.ts, scripts/shared-space-harness.mjs 읽기.
3. 현재 구현 요약: 하나의 THREE.Points/BufferGeometry, front는 (x,y), right는 (z,y), row별 count=max(frontRow,sideRow), 짧은 쪽 modulo 재사용, y active bounds 정규화, fixed blended per-point RGB, projection-only/top/fallback/view-opacity/depth gate 없음.
4. 첨부 이미지 알고리즘: 2-view row algorithm. A={(x,y):I_A(x,y)=1}, B={(z,y):I_B(z,y)=1}; X_r={x:(x,r)∈A}, Z_r={z:(z,r)∈B}; N_r=min(|X_r|,|Z_r|); p_k^(r)=(x_k,r,z_k); P=∪_r {p_k^(r)}.

목표:
현재 2view은 쉬운 알고리즘으로 가능했지만, 앞으로 아래 기능을 위해 더 수식적이고 검증 가능한 알고리즘이 필요하다.
1) 각 이미지마다 다른 색 적용
2) 각 방향에서 시선 방향에 따른 이미지의 작은 변화(팔이 움직인다거나 등)
3) 3view 추가

이번 탐색은 얕은 아이디어 나열 금지. 다음 관점으로 깊게 분석하라:

A. 수학적 feasibility
- 2-view는 row별 bipartite matching/transport로 볼 수 있는가?
- min 방식, max+reuse 방식, balanced transport 방식의 정확한 차이와 failure mode는?
- 3-view는 A(x,y), B(z,y), C(x,z)를 동시에 만족하는 3D 점/voxel/contingency table 문제다. Exact feasibility 조건은 무엇인가?
- 임의의 3개 이미지가 over-constrained일 때 soft constraint, slack, sparsity, occlusion, density regularization을 어떻게 둘 것인가?
- projection-only noise 없이 3-view를 추가하려면 어떤 조건을 QA로 강제해야 하는가?

B. 색/재질 feasibility
- 하나의 물리 점이 view별로 다른 색을 보이는 것을 per-view texture swap/opacity gate가 아닌 방식으로 어떻게 정당화할 수 있는가?
- directional BRDF, anisotropic splat, micro-lenticular/louvered point, angular color basis, spherical harmonics 또는 learned basis를 고려하라.
- 색이 바뀌는 것과 geometry/opacity가 바뀌는 것의 경계를 명확히 하라.

C. angular change / animation
- 카메라 direction θ에 따라 target image I_v,θ가 조금 달라지는 경우를 수식화하라.
- 점 위치를 고정하고 color/material만 변하게 할지, micro-displacement를 허용할지, 또는 multiple angular lobes를 둘지 비교하라.
- “팔이 움직인다”는 변화가 silhouette 변화라면 색만으로 가능한지, geometry가 필요한지 판단하라.

D. 실제 검증
- 현재 repo에서 바로 spike할 수 있는 executable experiments를 제안하라.
- 최소한 아래 실험 설계를 포함하라:
  1. row matching policy 비교: min vs max+reuse vs OT/balanced matching
  2. 3-view visual hull feasibility: front/right/top synthetic masks로 feasible voxel count와 projection IoU 측정
  3. directional color shader QA: view별 color target error와 중간각 smoothness 측정
  4. angular morph feasibility: canonical view 보존하면서 중간각 변화량 측정
- 각 실험의 입력, 출력, 성공/실패 기준, metric을 적어라.

최종 보고 형식(한국어):
1. 이번 탐색의 결론 한 문단
2. 현재 구현/첨부 이미지 알고리즘의 정확한 차이
3. 알고리즘 후보 5~7개. 각 후보마다:
   - 핵심 수식
   - 어떤 제약을 풀고 어떤 제약을 포기하는지
   - 2-view 적용성
   - per-view color 적용성
   - angular change 적용성
   - 3-view 적용성
   - failure mode
   - 검증 실험
   - 구현 난이도/추천도
4. 3-view exact/soft feasibility에 대한 별도 섹션. 여기서 가장 깊게 써라.
5. 실제 다음 1주일 spike 계획: 순서, 파일, 스크립트, metric, acceptance criteria.
6. 최종 추천: 지금 당장 구현할 알고리즘 1개, 병행 연구 1개, 보류 1개.

시간 사용:
- 단순히 바로 답하지 말고, repo를 읽고, 필요한 경우 작은 throwaway reasoning/script로 feasibility를 확인하라.
- 최대 1시간 이내에 완료하라.
