# E2 Review Compare Checkpoint

## Goal

Add a bounded `E2G` slice on top of review replay history so the operator can read a compact `action vs animation` compare focus for the selected package without turning `T2` into a full history browser.

## What Changed

- Added [demo_review_compare_state.py](C:/AiUE/tools/t2/python/aiue_t2/demo_review_compare_state.py) to derive a compact compare state from existing replay history.
- Extended [ui.py](C:/AiUE/tools/t2/python/aiue_t2/ui.py) and [ui_demo.py](C:/AiUE/tools/t2/python/aiue_t2/ui_demo.py) so `T2` now exposes:
  - `demo_review_compare_state`
  - `demo_review_compare_focus`
  - a compact compare summary inside the `Demo Review` panel
- Added the `E2G` gate:
  - [run_playable_demo_e2_review_compare.py](C:/AiUE/workflows/pmx_pipeline/run_playable_demo_e2_review_compare.py)
  - [run_playable_demo_e2_review_compare.ps1](C:/AiUE/run_playable_demo_e2_review_compare.ps1)

## What E2G Proves

- the compact replay history is now rich enough to produce a package-focused compare seam
- `T2 --latest --package-id <package> --dump-state-json --exit-after-load` can now recover:
  - the latest action replay event
  - the latest animation replay event
  - compare readiness
  - compare warning flags
- the compare seam stays evidence-first and bounded

## Out Of Scope

- full run-history browser
- side-by-side image canvas tooling
- packaged playable shell
- generalized operator console behavior

## Validation

- `pytest C:\\AiUE\\tests\\t2\\test_demo_review_compare_state.py -q`
- `pytest C:\\AiUE\\tests\\t2\\test_ui.py -q`
- `pytest C:\\AiUE\\tests\\t2\\test_process.py -q`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\\AiUE\\run_playable_demo_e2_review_compare.ps1 -WorkspaceConfig C:\\AiUE\\local\\pipeline_workspace.local.json`
