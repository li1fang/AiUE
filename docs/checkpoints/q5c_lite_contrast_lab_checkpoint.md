# Q5C-lite Contrast Lab Checkpoint

## Summary

This checkpoint adds a replayable `Q5C-lite` contrast lab on top of the existing passing volumetric inspection line.

It turns one passing `Q5C-lite` result into a small deterministic reference suite:

- `baseline_current`
- `best_pass_reference`
- `closest_fail_reference`

The goal is not new UE execution. The goal is to generate thicker pass/fail reference evidence from the already captured `q5a_host_result` payloads, so later `Q5C-lite` changes can be compared against stable nearby cases instead of isolated single reports.

## Changes

- Added [q5c_contrast.py](C:/AiUE/tools/t1/python/aiue_t1/q5c_contrast.py) with:
  - slot-origin `Z` perturbation
  - deterministic pass/fail search over fixed offsets
  - reference-case selection helpers
  - reusable suite output for workflow runners and tests
- Added [run_q5c_lite_contrast_lab.py](C:/AiUE/workflows/pmx_pipeline/run_q5c_lite_contrast_lab.py) and [run_q5c_lite_contrast_lab.ps1](C:/AiUE/run_q5c_lite_contrast_lab.ps1) as the internal runner surface
- Extended [report_index.py](C:/AiUE/tools/t1/python/aiue_t1/report_index.py) so `q5c_lite_contrast_lab` is treated as `platform_line`
- Extended [evidence_pack.py](C:/AiUE/tools/t1/python/aiue_t1/evidence_pack.py) so `T1` copies and previews the contrast lab debug images
- Added or extended tests in:
  - [test_q5c_contrast.py](C:/AiUE/tests/t1/test_q5c_contrast.py)
  - [test_report_index.py](C:/AiUE/tests/t1/test_report_index.py)
  - [test_evidence_pack.py](C:/AiUE/tests/t1/test_evidence_pack.py)

## Outcome

- `Q5C-lite` now has a lightweight contrast harness that produces a stable `safe vs fail` evidence trio for each current ready package.
- `T1` now surfaces those contrast images directly in the latest evidence pack.
- `T2` now sees the new report under `platform_line` without needing a dedicated new page.

## Validation

- `pytest C:\\AiUE\\tests\\t1\\test_q5c_contrast.py C:\\AiUE\\tests\\t1\\test_report_index.py C:\\AiUE\\tests\\t1\\test_evidence_pack.py C:\\AiUE\\tests\\t1\\test_q5c_lite.py C:\\AiUE\\tests\\t1\\test_q5c_lite_debug.py -q`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\\AiUE\\run_q5c_lite_contrast_lab.ps1 -WorkspaceConfig C:\\AiUE\\local\\pipeline_workspace.local.json`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\\AiUE\\tools\\run_t1_evidence_pack.ps1`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\\AiUE\\tools\\run_t2_workbench.ps1 -Latest -DumpStateJson -ExitAfterLoad`
