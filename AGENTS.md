# AGENTS.md — illusion-3d implementation guardrails

## Project invariant

This project is a browser/WebGL KAIST rendering artifact built around one shared 3D point cloud.

Non-negotiable:

```text
One physical point set P only.
For each point p=(x,y,z):
  Front +Z view projects (x,y) and should read the front reference image.
  Right +X view projects (z,y) and should read the side reference image.
```

Allowed:
- one contest `THREE.Points` object;
- one shared `THREE.BufferGeometry` for the contest cloud;
- fixed per-point positions;
- per-point front/side color attributes if the shader uses a directional material basis;
- shader glow/splat styling;
- helper axes/grid/labels as diagnostics only.

Forbidden:
- second point cloud for the second image;
- hidden image/text billboards;
- projection-only, fallback, top-only, or third-view-only points;
- view-dependent opacity gates;
- depth-test reading gates;
- texture swaps or per-view geometry swaps.

## Current implementation fact

`src/main.ts` now implements the target production candidate: `quantile_max` row materialization plus `cosine_s1` directional color using `frontColor`/`sideColor` endpoint attributes. Keep the harness strict gate green before claiming this remains true.

## Final target algorithm

### 1. Row materialization: `quantile_max`

For each matched row `y`:

```text
X_y = sorted active front x samples
Z_y = sorted active side z samples
N_y = max(|X_y|, |Z_y|)

x_k = X_y[floor((k + 0.5) |X_y| / N_y)]
z_k = Z_y[floor((k + 0.5) |Z_y| / N_y)]
p_k = (x_k, y, z_k)
```

Acceptance properties:
- `projectionOnlyPointCount = 0`;
- all matched-row active front samples covered;
- all matched-row active side samples covered;
- front/side multiplicity spread `<= 1`;
- `z_jump_gt25_ratio <= 0.01` in the algorithm/browser parity harness;
- `direction_flip_ratio_mean <= 0.01` in the algorithm/browser parity harness;
- front/side endpoint projection quality must not regress beyond the plan gate.

### 2. Directional color: `cosine_s1`

Each physical point should retain both endpoint colors:

```text
frontColor = A(x_k, y)
sideColor  = B(z_k, y)
```

At render time, for front-to-right angle `theta in [0°, 90°]`:

```text
wF(theta) = cos(theta) / (cos(theta) + sin(theta))
wR(theta) = sin(theta) / (cos(theta) + sin(theta))
c(theta) = wF(theta) * frontColor + wR(theta) * sideColor
```

Acceptance properties:
- front endpoint uses front color only;
- right endpoint uses side color only;
- no alpha-to-zero or opacity gate;
- no texture swap;
- max 5-degree color step metrics are reported before claiming quality.

## Required workflow before feature implementation

1. Read `CURRENT_HANDOFF.md`, `README.md`, this `AGENTS.md`, and `.hermes/plans/quantile-directional-implementation-plan-20260518.md`.
2. Run the current baseline checks:

```bash
npm run harness
npm run harness:algorithm
```

3. Implement the plan in small slices. Do row materialization before directional color.
4. After each slice, run:

```bash
npm run harness
npm run harness:algorithm
npm run build
```

5. For production readiness, also run the strict post-implementation gate:

```bash
npm run harness:algorithm:require-production
```

6. For visual claims, open the browser, check `window.__LENTICULAR_QA__`, inspect console errors, and save front/right/reveal evidence screenshots.

## Review roles

Use the role specs in `.hermes/agents/`:
- `implementation-agent.md` for code changes;
- `spec-review-agent.md` for algorithm/invariant compliance;
- `quality-review-agent.md` for maintainability and regression risk;
- `browser-qa-agent.md` for visual/browser evidence.

## Reporting standard

Be explicit about evidence versus inference:
- “script scan says source uses quantile_max/cosine_s1” is evidence;
- “should look better” is not evidence;
- browser screenshots and QA JSON are required before claiming final visual quality.
