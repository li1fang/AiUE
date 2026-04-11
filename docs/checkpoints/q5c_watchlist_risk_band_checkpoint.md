# Q5C-lite Watchlist Risk Band Checkpoint

## Summary

This checkpoint upgrades the `Q5C-lite` summary from a single focus margin into a small risk posture layer.

## Changes

- Extended [evidence_pack.py](C:/AiUE/tools/t1/python/aiue_t1/evidence_pack.py) so `quality_summaries.q5c_lite` now emits:
  - per-package `risk_band`
  - per-package `risk_reason`
  - top-level `risk_band_counts`
  - top-level `watchlist_package_ids`
  - top-level `watchlist_count`
  - top-level `highest_risk_band`
  - top-level `ordered_packages_by_risk`
- Fixed the first-band rules to stay simple and deterministic:
  - `fail`
  - `borderline`
  - `watch`
  - `stable`
- Extended the T1 HTML evidence pack so the `Q5C-lite` section now shows risk-band summary and watchlist posture.
- Extended [workbench_render.py](C:/AiUE/tools/t2/python/aiue_t2/workbench_render.py) so the native workbench summary strip now surfaces:
  - highest risk band
  - watchlist count
  - closest margin focus

## Outcome

- `Q5C-lite` can now say not only which package is closest to failure, but whether the current platform posture should be read as `stable` or already on a `watch` trajectory.
- On the current fixture and live shape, the narrowest margin still maps to a `watch` posture because the closest margin is only `0.02`.

## Validation

- `pytest C:\\AiUE\\tests\\t1 C:\\AiUE\\tests\\t2 -q`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\\AiUE\\tools\\run_t1_evidence_pack.ps1`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\\AiUE\\tools\\run_t2_workbench.ps1 -Latest -DumpStateJson -ExitAfterLoad`
