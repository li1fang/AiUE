# T2 Q5C Contrast Compare Mode Checkpoint

## Summary
- T2 now turns the Q5C contrast triptych into a compare surface instead of a picture-only surface.
- `q5c_contrast_focus` now includes `compare_mode_status`, `compare_summary_text`, and `compare_rows`.
- Compare rows are derived from the fixed triptych cases:
  - `baseline_current -> best_pass_reference`
  - `baseline_current -> closest_fail_reference`
  - `best_pass_reference -> closest_fail_reference`

## What Changed
- `tools/t2/python/aiue_t2/state.py`
  - Normalizes optional Q5C analysis metrics per case.
  - Builds compare rows with status/risk/diagnostic transitions and metric deltas.
- `tools/t2/python/aiue_t2/ui_sections.py`
  - Adds a native `ContrastComparePanel`.
- `tools/t2/python/aiue_t2/ui.py`
  - Mounts the compare panel in the main workbench.
- `tools/t2/python/aiue_t2/workbench_render.py`
  - Renders compare summaries alongside the triptych.

## Evidence Shape
- `q5c_contrast_focus.compare_summary_text`
- `q5c_contrast_focus.compare_rows[*].pair_label`
- `q5c_contrast_focus.compare_rows[*].status_transition`
- `q5c_contrast_focus.compare_rows[*].risk_transition`
- `q5c_contrast_focus.compare_rows[*].diagnostic_transition`
- `q5c_contrast_focus.compare_rows[*].delta_z_change`
- `q5c_contrast_focus.compare_rows[*].closest_margin_change`
- `q5c_contrast_focus.compare_rows[*].key_delta_text`

## Validation
- Targeted state/process/UI tests cover compare-mode state, dump output, and native rendering.
- The latest T2 smoke path still loads and renders without introducing a second compare-only code path.
