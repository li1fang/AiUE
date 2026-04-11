# Dynamic Balance Foundation Checkpoint

## Summary

This checkpoint records the first foundation slice for `Dynamic Balance Between Governance And Progress`.

The goal of this slice is not to add a new content capability.

It adds a small first-party mechanism that can answer:

- is the repo structurally healthy enough to keep moving flexibly?
- is the current pressure pushing us toward governance?
- is the current pressure pushing us toward stabilization?
- are we at risk of over-cleaning and starving progress?

## What Landed

- new ADR:
  - [ADR-0006-dynamic-balance-between-governance-and-progress.md](C:/AiUE/docs/adr/ADR-0006-dynamic-balance-between-governance-and-progress.md)
- new report generator:
  - [dynamic_balance.py](C:/AiUE/tools/t1/python/aiue_t1/dynamic_balance.py)
  - [run_dynamic_balance.py](C:/AiUE/tools/t1/python/run_dynamic_balance.py)
  - [run_dynamic_balance.ps1](C:/AiUE/tools/run_dynamic_balance.ps1)
- `T1 report_index` now classifies:
  - `active_line`
  - `platform_line`
  - `governance_line`
  - `historical_other`
- `T1 evidence pack` now exposes a balance summary card
- `T2` now reads `governance_balance` from the latest manifest and exposes it through:
  - report tree grouping
  - summary counts
  - `--dump-state-json`

## Fixed Policy In V1

The first version is fixed as:

- `soft_signal`
- `checkpoint_round`
- `recent_round_window = 6`
- `hotspot_touch_window = 3`
- `large_first_party_file_threshold_lines = 900`
- `critical_first_party_file_threshold_lines = 1800`
- `consecutive_governance_only_rounds_for_progress_pressure = 2`
- `consecutive_hotspot_touches_for_governance_pressure = 3`

The first version evaluates exactly:

- `stability_pressure`
- `governance_pressure`
- `progress_pressure`

The first version can recommend exactly:

- `stabilization`
- `governance`
- `progress`
- `flexible`

## Verification

The implementation was verified through:

- `python -m py_compile` on the new `dynamic_balance` module, updated `T1` modules, and updated `T2` state/UI/tests
- `C:\AiUE\.venv-tooling\Scripts\python.exe -m pytest tests\t1 -q`
  - `29 passed`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\AiUE\tools\run_t2_workbench_tests.ps1 -SkipPrepareLatestPack -SkipSoak`
  - `15 passed, 1 deselected`

The new fixture surface also confirms:

- `report_index` sees `governance_line`
- `T1` manifest carries `governance_line_reports`
- `T2` dump payload includes `governance_balance`
- no governance report still produces `governance_balance.status = missing` without crashing

## Boundary

This checkpoint deliberately stops short of:

- hard blocking feature work
- adding a special T2 balance tab
- adding checkpoint override workflows
- turning balance evaluation into a release gate

What it does add is the first project-health layer that is:

1. generated
2. latest-report based
3. evidence-pack visible
4. native-workbench readable

That is the right first level of seriousness for AiUE at its current stage.
