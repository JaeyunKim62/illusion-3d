#!/usr/bin/env bash
set -u
cd /c/00_Codes/illusion-3d || exit 1
LOG_DIR=.hermes/overnight-runs
mkdir -p "$LOG_DIR"
RUN_LOG="$LOG_DIR/lenticular-runner-$(date +%Y%m%d-%H%M%S).log"
echo "[runner] start $(date -Iseconds) branch=$(git branch --show-current)" | tee -a "$RUN_LOG"
for tick in 1 2 3 4 5 6; do
  echo "[runner] tick $tick start $(date -Iseconds)" | tee -a "$RUN_LOG"
  PROMPT="$(cat .hermes/plans/overnight-lenticular-tick-prompt.txt)

Tick number: $tick of 6. Keep this tick bounded."
  hermes -s webgl-3d-viewers -s subagent-driven-development chat -Q -q "$PROMPT" >> "$RUN_LOG" 2>&1
  code=$?
  echo "[runner] tick $tick exit_code=$code end $(date -Iseconds)" | tee -a "$RUN_LOG"
  if [ "$tick" != "6" ]; then
    echo "[runner] sleeping 45m before next tick" | tee -a "$RUN_LOG"
    sleep 2700
  fi
done
echo "[runner] complete $(date -Iseconds)" | tee -a "$RUN_LOG"
