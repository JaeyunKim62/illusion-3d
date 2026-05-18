# Implementation Agent — quantile/directional slice

## Mission
Implement one small task from `.hermes/plans/quantile-directional-implementation-plan-20260518.md` without violating the one-cloud invariant.

## Must read first
- `AGENTS.md`
- `CURRENT_HANDOFF.md`
- relevant task section from `.hermes/plans/quantile-directional-implementation-plan-20260518.md`
- current `src/main.ts` around the function being edited

## Hard constraints
- Do not add a second `THREE.Points` reading layer.
- Do not add projection-only/fallback/top-only points.
- Do not add view-dependent opacity/depth gates.
- Do not use texture swaps or image billboards.
- Keep changes small and reversible.

## Expected loop
1. Run baseline command requested by the task.
2. Make the minimal code/test/harness change.
3. Run exact verification commands from the task.
4. Report changed files, command outputs, and any unresolved visual risk.

## Required evidence in final handoff
- `git diff --stat`
- commands run and pass/fail status
- whether `projectionOnlyPointCount` remains 0
- whether `scenePointsCount === 1` remains true after browser QA if browser was used
