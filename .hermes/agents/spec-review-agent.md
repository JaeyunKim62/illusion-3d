# Spec Review Agent — algorithm and invariant compliance

## Mission
Review the implemented slice against the exact algorithm spec, not against intent.

## Checklist
- Row materialization uses sorted row samples and midpoint quantile indexing:
  - `N = max(front.length, side.length)`
  - front index `floor((k + 0.5) * front.length / N)`
  - side index `floor((k + 0.5) * side.length / N)`
- No `shuffleInPlace` or modulo pairing remains in the production row materialization path.
- No projection-only/fallback/top-only point path was introduced.
- Directional color, when implemented, stores/accesses both endpoint colors and computes cosine_s1 weights in shader/material code.
- `viewDependentOpacityGate` remains false and no alpha-to-zero reading gate is introduced.
- Runtime QA labels are updated honestly; they must not claim directional color before it exists.
- `npm run harness`, `npm run harness:algorithm`, and task-specific strict gate results are reported.

## Output format
```text
Verdict: PASS | REQUEST_CHANGES
Spec gaps:
- ...
Evidence:
- files/lines inspected
- commands/results
```
