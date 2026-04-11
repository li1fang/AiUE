# T2 Q5C Contrast Focus Checkpoint

## Summary

This checkpoint upgrades `T2` from merely listing the `q5c_lite_contrast_lab` report to directly consuming its package-level reference cases.

The result is a small native workbench loop for `Q5C-lite` contrast evidence:

- choose a package
- see the current `baseline / safe / fail` trio
- jump the preview selection directly from the contrast list
- read the same focus object from `--dump-state-json`

## Changes

- Extended [state.py](C:/AiUE/tools/t2/python/aiue_t2/state.py) with:
  - `q5c_contrast` summary extraction from the copied latest report
  - `build_q5c_contrast_focus(...)`
  - default-image preference for the contrast baseline when present
- Extended [state_models.py](C:/AiUE/tools/t2/python/aiue_t2/state_models.py) so native dump payloads now expose:
  - `q5c_contrast_focus`
- Extended [ui.py](C:/AiUE/tools/t2/python/aiue_t2/ui.py) with:
  - `q5c_contrast_summary`
  - `q5c_contrast_case_list`
- Extended [workbench_render.py](C:/AiUE/tools/t2/python/aiue_t2/workbench_render.py) so:
  - the selected package drives contrast focus
  - contrast cases render as a native list
  - selecting a contrast case jumps the preview image
- Extended `T2` fixtures and tests in:
  - [helpers.py](C:/AiUE/tests/t2/helpers.py)
  - [test_state.py](C:/AiUE/tests/t2/test_state.py)
  - [test_process.py](C:/AiUE/tests/t2/test_process.py)
  - [test_ui.py](C:/AiUE/tests/t2/test_ui.py)

## Outcome

- `T2` now has a direct native read surface for `Q5C-lite` contrast evidence, instead of forcing users to inspect the raw report JSON or scroll the full preview list.
- Live `dump-state-json` now exposes `q5c_contrast_focus`, including:
  - `selected_package_id`
  - `case_ids`
  - `recommended_preview_image_key`
  - per-case image paths and risk context
- Live workbench startup now defaults to the contrast baseline image when the latest pack contains `Q5C-lite` contrast evidence.

## Validation

- `pytest C:\\AiUE\\tests\\t2\\test_state.py C:\\AiUE\\tests\\t2\\test_process.py::test_workbench_cli_reads_q5c_quality_summary C:\\AiUE\\tests\\t2\\test_ui.py::test_workbench_window_shows_q5c_quality_summary -q`
- `pytest C:\\AiUE\\tests\\t2 -q`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\\AiUE\\tools\\run_t2_workbench.ps1 -Latest -DumpStateJson -ExitAfterLoad`
