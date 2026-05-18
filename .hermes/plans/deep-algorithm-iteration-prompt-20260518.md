사용자는 “1시간 동안 반복해서 알고리즘을 탐색하고 검증하라”고 명시했다. 한 번 보고서 작성으로 끝내지 말고, 1시간 동안 여러 iteration을 돌며 이전 산출물을 비판/보강/검증하라.

작업 디렉터리: C:\00_Codes\illusion-3d
브랜치 기대값: algorithm-exploration-20260518

절대 금지:
- production 파일(src/main.ts, scripts/shared-space-harness.mjs 등) 수정 금지
- projection-only/top/fallback point를 production에 추가 금지

허용:
- artifacts/algorithm-exploration/ 아래 연구 보고서/검증 계획/실험 결과 작성
- artifacts/.hermes/ 아래 throwaway scripts 작성/실행

반드시 할 일:
1. 현재까지 산출물 읽기:
   - artifacts/algorithm-exploration/deep-algorithm-proposal-20260518.md
   - artifacts/algorithm-exploration/verification-plan-20260518.md
   - artifacts/.hermes/algorithm_exploration_probe_20260518.json
2. 이전 결론을 비판하라. “무엇이 아직 얕은가?”, “어떤 수식/조건이 빠졌는가?”, “무슨 실험이 실제 이미지를 쓰지 않아 약한가?”를 명시하라.
3. 이번 iteration에서는 최소 하나 이상의 구체적 진전을 만들어라. 예:
   - 3-view exact feasibility의 더 엄밀한 graph/tensor 조건 정리
   - row OT materialization/rounding 방식 비교
   - directional color lobe의 중간각 pop 문제를 줄이는 basis/regularizer 제안
   - angular morph가 색-only로 가능한 경우와 geometry-needed인 경우의 판정법
   - 실제 reference image 기반 실험 스크립트 초안/의사코드/metric 강화
4. 산출물을 append 또는 새 파일로 저장하라:
   - artifacts/algorithm-exploration/iterative-deepening-log-20260518.md
   - 필요시 artifacts/algorithm-exploration/iteration-N-*.md/json
5. 마지막 iteration이면 최종 종합을 저장하라:
   - artifacts/algorithm-exploration/final-one-hour-algorithm-recommendation-20260518.md

최종 보고 요구:
- 한국어
- 반복 횟수, 각 iteration에서 새로 얻은 것, 남은 불확실성, 최종 추천을 명시
- 단순 후보 나열 금지. 수학적 feasibility, 검증 metric, 구현 spike 순서 중심으로 정리
