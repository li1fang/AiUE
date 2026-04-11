# T2 State Models Governance Checkpoint

## Goal

Reduce hotspot pressure in [state.py](C:/AiUE/tools/t2/python/aiue_t2/state.py) without changing the T2 dump-state surface, demo request selection behavior, or workbench loading contract.

## What Changed

- Extracted the T2 state model layer into [state_models.py](C:/AiUE/tools/t2/python/aiue_t2/state_models.py).
- Moved these stable definitions out of the previous hotspot file:
  - category labels/order
  - `ErrorRecord`
  - `ReportRecord`
  - `PreviewImageRecord`
  - `DemoPresetRecord`
  - `DemoPackageRecord`
  - `DemoSessionRecord`
  - `DemoRequestRecord`
  - `GovernanceBalanceRecord`
  - `AppState`
  - `ViewState`
- Kept [state.py](C:/AiUE/tools/t2/python/aiue_t2/state.py) as the compatibility-facing module for:
  - manifest/session loading
  - report and preview extraction
  - demo request construction
  - existing imports from the rest of `T2`

## Structural Result

- [state.py](C:/AiUE/tools/t2/python/aiue_t2/state.py) is now reduced to `642` lines.
- The model layer now has an explicit module boundary instead of living inside the same loader/request hotspot.
- Existing imports from `aiue_t2.state` remain valid, so this is a governance cut rather than an API migration.

## Validation

- `python -m py_compile C:\\AiUE\\tools\\t2\\python\\aiue_t2\\state.py C:\\AiUE\\tools\\t2\\python\\aiue_t2\\state_models.py`
- `pytest C:\\AiUE\\tests\\t2\\test_state.py -q`
- `pytest C:\\AiUE\\tests\\t2 -q`

## Why This Matters

This is a deliberately small governance slice. It lowers the cost of future work on the T2 loading/request seam while keeping the repo on the same evidence-first control path.
