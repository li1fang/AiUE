# T2 Windows Native Workbench Checkpoint

## Summary

`T2` upgrades the `T1` static evidence layer into a repo-managed Windows desktop workbench.

It remains read-only by design:

- it does not replace existing gates
- it does not launch Unreal tasks
- it consumes the existing `T1` evidence pack and latest reports

The purpose of `T2` is to make current evidence easier to inspect locally while also exposing a machine-readable native-tool state for automation.

## What Landed

- new PySide6 desktop workbench under `tools/t2/python/aiue_t2/`
- shared state/model loader for:
  - `manifest.json`
  - copied report artifacts
  - preview images
  - slot debugger payload
- stable native-tool dump surface:
  - `--dump-state-json`
  - `--exit-after-load`
- Windows wrapper entry points:
  - `tools/run_t2_workbench.ps1`
  - `tools/run_t2_workbench_tests.ps1`
- UI surfaces for:
  - summary cards
  - grouped report tree
  - JSON report detail
  - preview images and before/after metrics
  - slot debugger table

## Verification

The following verification was completed for `T2`:

- non-soak test slice:
  - `python -m pytest tests/t2 -q -m "not soak"`
  - result: `8 passed`
- full `T2` suite through the wrapper:
  - `powershell -NoProfile -ExecutionPolicy Bypass -File C:\AiUE\tools\run_t2_workbench_tests.ps1`
  - result: `9 passed`
- required stability checks were included in the full suite:
  - `7` open cycles
  - `3` error injections
  - one `5` minute short soak

Latest live smoke is based on:

- `Saved/tooling/t1/latest/manifest.json`

## Notes

- `T2` uses the same repo-managed tooling environment as `T1`: `C:\AiUE\.venv-tooling`
- the tooling requirements now explicitly include `Pillow`, because `T1` image metrics already depended on `PIL`
- `T2` is intentionally not packaged as `.exe` in this checkpoint; packaging remains a later discussion
