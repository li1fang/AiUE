# Q5C-lite Diagnostic Classification Checkpoint

## Goal

Make `Q5C-lite` failures easier to diagnose by adding a stable diagnostic class layer on top of the existing raw threshold failures.

## What Changed

- Extended [q5c_lite.py](C:/AiUE/tools/t1/python/aiue_t1/q5c_lite.py) so analysis now emits:
  - `fit_diagnostic_class`
  - `diagnostic_signals`
  - `threshold_deltas`
- Extended `penetration_clusters` metadata so each cluster now records:
  - `cluster_class`
  - `source_envelope`
  - `threshold_ratio`
  - `excess_ratio`
  - `intersection`
- Extended [run_volumetric_inspection_q5c_lite.py](C:/AiUE/workflows/pmx_pipeline/run_volumetric_inspection_q5c_lite.py) so per-package results and top-level counts now summarize:
  - floating-fit failures
  - penetration failures
  - mixed penetration+floating failures
  - borderline passes
- Extended [q5c_lite_debug.py](C:/AiUE/tools/t1/python/aiue_t1/q5c_lite_debug.py) so debug artifacts now print the diagnostic class directly.

## What This Proves

- `Q5C-lite` failures no longer read like a bag of threshold trips.
- The quality line can now distinguish:
  - `input_invalid`
  - `floating_fit_out_of_range`
  - `penetration_keepout_overlap`
  - `mixed_penetration_and_floating`
  - `pass_borderline`
  - `pass_stable`

## Validation

- `pytest C:\\AiUE\\tests\\t1\\test_q5c_lite.py -q`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\\AiUE\\run_volumetric_inspection_q5c_lite.ps1 -WorkspaceConfig C:\\AiUE\\local\\pipeline_workspace.local.json`
