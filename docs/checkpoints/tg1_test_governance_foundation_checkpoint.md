# TG1 Test Governance Foundation Checkpoint

## Summary
- Adds the first repo-native test governance layer.
- Introduces a machine-readable coverage ledger plus a generated governance report.
- Keeps governance as a soft signal, but adds a light checkpoint threshold through minimum required lanes.

## What Changed
- `ADR-0007` formalizes the first-round test governance policy.
- A coverage ledger now records what is covered, partial, or still missing.
- A new local governance runner computes required lanes from the current changed path surface and emits a latest governance report.
- `T1/T2` consume the new governance signal.
- `tools/t2/python/aiue_t2/state.py` is split into quality/demo helpers plus a smaller facade.

## Expected Current Truth
- Mainline remains viable.
- Coverage remains incomplete.
- Current expected governance result is `attention`, primarily because:
  - `material_texture_loading` is still missing
  - `manual_playable_demo_validation` is still missing
