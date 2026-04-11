# E2 Review Compare Browse Checkpoint

## Goal

Add a bounded `E2H` slice so the operator can move across the latest two compare pairs for a selected package and jump straight to the paired `action` / `animation` after-artifacts without turning `T2` into a full history browser.

## What Changed

- Extended [demo_review_compare_state.py](C:/AiUE/tools/t2/python/aiue_t2/demo_review_compare_state.py) so compare state now preserves bounded `compare_pairs` and can focus a selected pair index.
- Extended the native workbench selection seam through:
  - [app.py](C:/AiUE/tools/t2/python/aiue_t2/app.py)
  - [state.py](C:/AiUE/tools/t2/python/aiue_t2/state.py)
  - [ui.py](C:/AiUE/tools/t2/python/aiue_t2/ui.py)
  - [ui_demo.py](C:/AiUE/tools/t2/python/aiue_t2/ui_demo.py)
  - [workbench_demo_ops.py](C:/AiUE/tools/t2/python/aiue_t2/workbench_demo_ops.py)
  - [workbench_render.py](C:/AiUE/tools/t2/python/aiue_t2/workbench_render.py)
- `T2` now accepts `--review-compare-index` and the `Demo Review` panel now provides:
  - `Newer Compare`
  - `Older Compare`
  - `Open Compared Action After`
  - `Open Compared Animation After`
- Added the `E2H` gate:
  - [run_playable_demo_e2_review_compare_browse.py](C:/AiUE/workflows/pmx_pipeline/run_playable_demo_e2_review_compare_browse.py)
  - [run_playable_demo_e2_review_compare_browse.ps1](C:/AiUE/run_playable_demo_e2_review_compare_browse.ps1)

## What E2H Proves

- the current compact compare seam is rich enough to expose at least `2` bounded compare pairs per ready package
- `T2 --latest --package-id <package> --review-compare-index 0|1 --dump-state-json --exit-after-load` can now deterministically recover the requested pair
- the native operator can move from compare summary to the right after-artifacts without reopening raw history JSON

## Out Of Scope

- full replay-history browser
- side-by-side image canvas tooling
- packaged playable shell
- generalized operator console behavior

## Validation

- `pytest C:\\AiUE\\tests\\t2\\test_demo_review_compare_state.py -q`
- `pytest C:\\AiUE\\tests\\t2\\test_ui.py -q`
- `pytest C:\\AiUE\\tests\\t2\\test_process.py -q`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\\AiUE\\run_playable_demo_e2_review_compare_browse.ps1 -WorkspaceConfig C:\\AiUE\\local\\pipeline_workspace.local.json`
