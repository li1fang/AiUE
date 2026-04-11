# T2 Q5C Contrast Triptych Checkpoint

## Summary

This checkpoint upgrades the `T2` native `Q5C` contrast focus from a list-only selector into a direct triptych preview.

The workbench now shows the three reference cases as first-class native visuals:

- `baseline_current`
- `best_pass_reference`
- `closest_fail_reference`

## Changes

- Extended [ui_sections.py](C:/AiUE/tools/t2/python/aiue_t2/ui_sections.py) with:
  - shared image-label rendering helper
  - `ContrastTriptychPanel`
- Extended [ui.py](C:/AiUE/tools/t2/python/aiue_t2/ui.py) so the workbench now mounts:
  - `q5c_contrast_triptych`
- Extended [workbench_render.py](C:/AiUE/tools/t2/python/aiue_t2/workbench_render.py) so:
  - contrast focus always renders a native triptych
  - package switches update the contrast gallery
  - case selection still drives the main preview list
  - resize events re-render both the main preview and the triptych
- Extended [test_ui.py](C:/AiUE/tests/t2/test_ui.py) so the native workbench tests now assert:
  - contrast triptych hidden when absent
  - contrast triptych visible when present
  - baseline / best-pass / closest-fail titles render
  - baseline pixmap actually loads

## Outcome

- `T2` now presents the `Q5C-lite` contrast suite as an actual `safe vs fail` visual trio, not just as JSON or a list of keys.
- The user can still click a case row to jump the main preview, but the three-way comparison is now visible without extra navigation.
- This makes the contrast lab meaningfully closer to a review surface instead of a hidden internal artifact.

## Validation

- `pytest C:\\AiUE\\tests\\t2\\test_ui.py::test_workbench_window_renders_fixture_pack C:\\AiUE\\tests\\t2\\test_ui.py::test_workbench_window_shows_q5c_quality_summary C:\\AiUE\\tests\\t2\\test_state.py::test_load_workbench_state_reads_q5c_contrast_focus C:\\AiUE\\tests\\t2\\test_process.py::test_workbench_cli_reads_q5c_quality_summary -q`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\\AiUE\\tools\\run_t2_workbench.ps1 -Latest -DumpStateJson -ExitAfterLoad`
