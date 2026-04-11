# Q5C-lite Focus Margin Summary Checkpoint

## Summary

This checkpoint upgrades the `Q5C-lite` tooling summary from simple pass/fail aggregation into a proactive margin view.

## Changes

- Extended [evidence_pack.py](C:/AiUE/tools/t1/python/aiue_t1/evidence_pack.py) so `quality_summaries.q5c_lite` now records:
  - `focus_package_id`
  - `focus_metric`
  - `focus_margin_to_failure`
  - per-package `margin_to_failure_by_metric`
  - per-package `closest_margin_metric`
  - per-package `closest_margin_value`
- Extended the T1 HTML evidence summary so `Q5C-lite` now shows the current closest threshold margin instead of only diagnostic class counts.
- Extended the T2 native summary strip so operators can immediately see which package is currently closest to failure and on which metric.
- Added regression coverage in:
  - [test_evidence_pack.py](C:/AiUE/tests/t1/test_evidence_pack.py)
  - [test_state.py](C:/AiUE/tests/t2/test_state.py)
  - [test_process.py](C:/AiUE/tests/t2/test_process.py)
  - [test_ui.py](C:/AiUE/tests/t2/test_ui.py)

## Outcome

- `Q5C-lite` can now answer both:
  - “did the gate pass?”
  - “which package is currently closest to failing next?”
- This makes the quality line more useful for proactive follow-up without inventing a new gate.

## Validation

- `pytest C:\\AiUE\\tests\\t1 C:\\AiUE\\tests\\t2 -q`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\\AiUE\\tools\\run_t1_evidence_pack.ps1`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\\AiUE\\tools\\run_t2_workbench.ps1 -Latest -DumpStateJson -ExitAfterLoad`
