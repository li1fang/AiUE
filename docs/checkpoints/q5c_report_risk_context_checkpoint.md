# Q5C-lite Report Risk Context Checkpoint

## Summary

This checkpoint pushes the recent `Q5C-lite` watchlist logic down into the original per-package inspection result, instead of keeping it only in `T1` summary code.

## Changes

- Extended [q5c_lite.py](C:/AiUE/tools/t1/python/aiue_t1/q5c_lite.py) with reusable helpers for:
  - margin normalization
  - closest-margin selection
  - `risk_band` classification
  - `risk_reason` formatting
- Extended [run_volumetric_inspection_q5c_lite.py](C:/AiUE/workflows/pmx_pipeline/run_volumetric_inspection_q5c_lite.py) so each package result now writes:
  - `margin_to_failure_by_metric`
  - `closest_margin_metric`
  - `closest_margin_value`
  - `risk_band`
  - `risk_reason`
- Extended [q5c_lite_debug.py](C:/AiUE/tools/t1/python/aiue_t1/q5c_lite_debug.py) so the debug artifact now renders:
  - risk band
  - limiting metric
  - full margin vector
- Extended [evidence_pack.py](C:/AiUE/tools/t1/python/aiue_t1/evidence_pack.py) so `T1` prefers report-native risk context when it exists, and only falls back to local recomputation for older reports.

## Outcome

- `Q5C-lite` risk posture is now part of the source report itself, not just a derived `T1` summary.
- The per-package debug artifact is now a stronger negative-evidence object because it explains not only geometry but also why the package is currently `watch` or `borderline`.
- `T1` and `T2` stay aligned with the raw report rather than silently recomputing a parallel interpretation.

## Validation

- `pytest C:\\AiUE\\tests\\t1\\test_q5c_lite.py C:\\AiUE\\tests\\t1\\test_q5c_lite_debug.py C:\\AiUE\\tests\\t1\\test_evidence_pack.py C:\\AiUE\\tests\\t2\\test_state.py C:\\AiUE\\tests\\t2\\test_process.py C:\\AiUE\\tests\\t2\\test_ui.py -q`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\\AiUE\\run_volumetric_inspection_q5c_lite.ps1 -WorkspaceConfig C:\\AiUE\\local\\pipeline_workspace.local.json`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\\AiUE\\tools\\run_t1_evidence_pack.ps1`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\\AiUE\\tools\\run_t2_workbench.ps1 -Latest -DumpStateJson -ExitAfterLoad`
