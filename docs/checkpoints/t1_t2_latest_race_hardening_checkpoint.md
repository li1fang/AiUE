# T1/T2 Latest Race Hardening Checkpoint

## Summary

This checkpoint hardens the handoff between `T1` evidence-pack refresh and `T2 -Latest` consumption.

## Problem

We reproduced a real race where:

1. `run_t1_evidence_pack.ps1` refreshed `Saved/tooling/t1/latest`
2. `run_t2_workbench.ps1 -Latest` read the same path at the same time
3. `T2` occasionally observed a transient `manifest_missing`

The previous implementation removed `latest` before copying the new tree, which created a visible gap.

## Changes

- Extended [evidence_pack.py](C:/AiUE/tools/t1/python/aiue_t1/evidence_pack.py) with a staged latest refresh helper:
  - copy new pack into an `__incoming__` sibling
  - move existing `latest` aside to a `__backup__` sibling
  - swap staged content into `latest`
  - clean backup after success
- Extended [state.py](C:/AiUE/tools/t2/python/aiue_t2/state.py) with `wait_for_manifest_path(...)`
- Extended [app.py](C:/AiUE/tools/t2/python/aiue_t2/app.py) so `T2` now waits briefly for the latest manifest when launched in `--latest` mode
- Added regression coverage in:
  - [test_evidence_pack.py](C:/AiUE/tests/t1/test_evidence_pack.py)
  - [test_state.py](C:/AiUE/tests/t2/test_state.py)

## Outcome

- `latest` refresh is no longer implemented as `delete then copy`
- `T2 -Latest` is more tolerant of short refresh windows instead of failing immediately
- Sequential `T1 -> T2` smoke remains the preferred verification order, but transient latest refresh races are now much less fragile

## Validation

- `pytest C:\\AiUE\\tests\\t1\\test_evidence_pack.py C:\\AiUE\\tests\\t2\\test_state.py -q`
- `pytest C:\\AiUE\\tests\\t1 C:\\AiUE\\tests\\t2 -q`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\\AiUE\\tools\\run_t1_evidence_pack.ps1`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\\AiUE\\tools\\run_t2_workbench.ps1 -Latest -DumpStateJson -ExitAfterLoad`
