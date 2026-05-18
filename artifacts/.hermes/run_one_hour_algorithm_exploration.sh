#!/usr/bin/env bash
set -u
ROOT="$(pwd)"
mkdir -p artifacts/algorithm-exploration artifacts/.hermes .hermes/algorithm-exploration
LOG=".hermes/algorithm-exploration/one-hour-iterative-run-20260518.log"
STATE="artifacts/algorithm-exploration/iterative-deepening-log-20260518.md"
FINAL="artifacts/algorithm-exploration/final-one-hour-algorithm-recommendation-20260518.md"
PROMPT_FILE=".hermes/plans/deep-algorithm-iteration-prompt-20260518.md"
START=$(date +%s)
END=$((START + 3600))
ITER=1
{
  echo "=== one-hour iterative algorithm exploration start $(date '+%Y-%m-%d %H:%M:%S %z') ==="
  echo "workdir=$ROOT"
  echo "branch=$(git branch --show-current 2>/dev/null || true)"
  echo "" 
} >> "$LOG"

if [ ! -f "$STATE" ]; then
  cat > "$STATE" <<'MD'
# Iterative deepening log — 2026-05-18

This file is appended by the one-hour algorithm exploration runner.
MD
fi

while [ $(date +%s) -lt $END ]; do
  NOW=$(date +%s)
  REM=$((END - NOW))
  if [ $REM -lt 240 ]; then
    break
  fi
  echo "=== iteration $ITER start $(date '+%Y-%m-%d %H:%M:%S %z') remaining=${REM}s ===" >> "$LOG"
  ITER_PROMPT="$(cat "$PROMPT_FILE")

이번은 iteration $ITER 이다. 현재까지의 iterative log와 기존 보고서를 읽고, 새로 비판/보강/검증하라. 이 iteration 결과를 artifacts/algorithm-exploration/iterative-deepening-log-20260518.md 에 append하라. 가능하면 iteration-specific 파일도 만들어라. 종료 전이 아니어도 다음 iteration이 이어받을 수 있게 open questions를 남겨라."
  hermes chat -Q -t terminal,file,web -q "$ITER_PROMPT" >> "$LOG" 2>&1
  EC=$?
  echo "=== iteration $ITER end $(date '+%Y-%m-%d %H:%M:%S %z') exit=$EC ===" >> "$LOG"
  if [ $EC -ne 0 ]; then
    echo "iteration $ITER failed exit=$EC; continuing after short pause" >> "$LOG"
  fi
  ITER=$((ITER + 1))
  sleep 20
 done

FINAL_PROMPT="$(cat "$PROMPT_FILE")

이제 1시간 반복 탐색의 최종 종합을 작성하라. iterative-deepening-log-20260518.md, deep-algorithm-proposal-20260518.md, verification-plan-20260518.md, probe json, iteration 파일들을 모두 읽고 최종 결론을 artifacts/algorithm-exploration/final-one-hour-algorithm-recommendation-20260518.md 에 저장하라. 한국어로 작성하고, 반복 횟수/검증 근거/수학적 조건/최종 구현 우선순위를 명시하라."

echo "=== final synthesis start $(date '+%Y-%m-%d %H:%M:%S %z') iterations_completed=$((ITER-1)) ===" >> "$LOG"
hermes chat -Q -t terminal,file,web -q "$FINAL_PROMPT" >> "$LOG" 2>&1
EC=$?
echo "=== final synthesis end $(date '+%Y-%m-%d %H:%M:%S %z') exit=$EC ===" >> "$LOG"
echo "=== one-hour iterative algorithm exploration end $(date '+%Y-%m-%d %H:%M:%S %z') total_iterations=$((ITER-1)) final_exit=$EC ===" >> "$LOG"
exit $EC
