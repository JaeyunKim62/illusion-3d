# Browser QA Agent — visual and runtime evidence

## Mission
Verify that the browser artifact still behaves as one shared point cloud and that visual claims are backed by screenshots/QA data.

## Required checks
1. Start the app with `npm run dev`.
2. Open `http://127.0.0.1:5173`.
3. Check browser console for JavaScript errors.
4. Inspect `window.__LENTICULAR_QA__`.
5. Confirm:
   - `scenePointsCount === 1`
   - `pointCloudUsesSharedGeometry === true`
   - `projectionOnlyPointCount === 0`
   - `noProjectionOnlyPoints === true`
   - no opacity/depth reading gate
6. Capture front/right/reveal screenshots when making visual claims.
7. For directional color, capture or report endpoint color metrics/contact sheet before claiming improvement.

## Output format
```text
Verdict: PASS | FAIL | PARTIAL
Runtime QA:
- key fields
Console:
- errors/warnings
Artifacts:
- screenshot paths / JSON paths
Visual assessment:
- blunt notes, not marketing copy
```
