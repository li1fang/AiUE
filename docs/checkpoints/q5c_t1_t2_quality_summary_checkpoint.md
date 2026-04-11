# Q5C-lite T1/T2 Quality Summary Checkpoint

## Summary

This checkpoint turns `Q5C-lite` from a report-only quality layer into a first-class tooling summary that can be consumed by both `T1` and `T2`.

## Changes

- Extended [evidence_pack.py](C:/AiUE/tools/t1/python/aiue_t1/evidence_pack.py) so the generated manifest now includes:
  - `quality_summaries.q5c_lite`
  - per-package diagnostic class, ratios, threshold deltas, and debug image linkage
- Extended the T1 HTML evidence pack with a dedicated `Q5C-lite Quality Summary` section.
- Extended T2 state loading so [state.py](C:/AiUE/tools/t2/python/aiue_t2/state.py) now reads `quality_summaries` and resolves copied debug image paths.
- Extended [state_models.py](C:/AiUE/tools/t2/python/aiue_t2/state_models.py) and [workbench_render.py](C:/AiUE/tools/t2/python/aiue_t2/workbench_render.py) so `dump-state-json` and the native workbench summary surface now expose the `Q5C-lite` status directly.
- Added fixture and regression coverage in:
  - [test_evidence_pack.py](C:/AiUE/tests/t1/test_evidence_pack.py)
  - [helpers.py](C:/AiUE/tests/t2/helpers.py)
  - [test_state.py](C:/AiUE/tests/t2/test_state.py)
  - [test_process.py](C:/AiUE/tests/t2/test_process.py)
  - [test_ui.py](C:/AiUE/tests/t2/test_ui.py)

## Outcome

- `Q5C-lite` is now easier to inspect programmatically because the latest `T1` manifest carries a stable summary object instead of forcing every consumer to re-parse the full report.
- `T2` can now show and dump the current `Q5C-lite` diagnostic posture even when the operator does not manually open the raw report JSON.
- The live workbench state now exposes which packages are currently `pass_stable` versus other future diagnostic classes.

## Validation

- `pytest C:\\AiUE\\tests\\t1 C:\\AiUE\\tests\\t2 -q`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\\AiUE\\tools\\run_t1_evidence_pack.ps1`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\\AiUE\\tools\\run_t2_workbench.ps1 -Latest -DumpStateJson -ExitAfterLoad`
