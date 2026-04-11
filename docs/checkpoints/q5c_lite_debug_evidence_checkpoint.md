# Q5C-lite Debug Evidence Checkpoint

## Goal

Upgrade `Q5C-lite` from a numbers-only volumetric report into an evidence-first local-fit checkpoint by generating a per-package debug artifact that makes the slot bounds, local-fit envelope, and keepout region visually inspectable.

## What Changed

- Added [q5c_lite_debug.py](C:/AiUE/tools/t1/python/aiue_t1/q5c_lite_debug.py) to render deterministic local-fit debug PNGs.
- Extended [q5c_lite.py](C:/AiUE/tools/t1/python/aiue_t1/q5c_lite.py) so the analysis payload now keeps:
  - `body_bounds_world`
  - `local_fit_intersection`
  - `penetration_intersection`
- Extended [run_volumetric_inspection_q5c_lite.py](C:/AiUE/workflows/pmx_pipeline/run_volumetric_inspection_q5c_lite.py) so every package now emits:
  - `artifacts.q5c_debug_image_path`
- Extended [evidence_pack.py](C:/AiUE/tools/t1/python/aiue_t1/evidence_pack.py) so `Q5C-lite` debug images enter the T1 preview gallery and therefore become visible to `T2` without a new UI page.

## What This Proves

- `Q5C-lite` is now easier to replay and diagnose because its local-fit decision has a visual debug companion instead of only scalar ratios.
- The quality line continues to stay evidence-first:
  - `Q5A` shows visible conflicts
  - `Q5B.x` shows richer spatial evidence
  - `Q5C-lite` now shows a local volumetric debug view

## Validation

- `pytest C:\\AiUE\\tests\\t1\\test_q5c_lite.py -q`
- `pytest C:\\AiUE\\tests\\t1\\test_q5c_lite_debug.py -q`
- `pytest C:\\AiUE\\tests\\t1\\test_evidence_pack.py -q`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\\AiUE\\run_volumetric_inspection_q5c_lite.ps1 -WorkspaceConfig C:\\AiUE\\local\\pipeline_workspace.local.json`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\\AiUE\\tools\\run_t1_evidence_pack.ps1`
