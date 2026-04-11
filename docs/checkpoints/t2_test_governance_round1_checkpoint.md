# T2 Test Governance Round 1

## Summary
- First-round test governance stays intentionally light.
- The goal is to stop treating every T2 change as either “run everything” or “trust vibes”.

## Policy
- `smoke`
  - Fast confidence lane for targeted state/process/UI checks.
  - Intended for tight edit loops and checkpoint packaging.
- `default`
  - Existing broad T2 regression lane.
- `full`
  - Same test surface as broad regression, with soak controlled separately.

## Tooling Entry
- `tools/run_t2_workbench_tests.ps1 -Profile smoke`
- `tools/run_t2_workbench_tests.ps1 -Profile default`
- `tools/run_t2_workbench_tests.ps1 -Profile full`

## Current Smoke Scope
- `tests/t2/test_state.py::test_load_workbench_state_reads_q5c_contrast_focus`
- `tests/t2/test_process.py::test_workbench_cli_reads_q5c_quality_summary`
- `tests/t2/test_ui.py::test_workbench_window_shows_q5c_quality_summary`

## Why This Is Enough For Round 1
- It gives us one stable fast lane around the newest Q5C/T2 evidence surface.
- It does not invent a heavy test taxonomy before we need it.
- It creates a clean place to evolve later into richer suite governance if turnaround or flake pressure rises.
