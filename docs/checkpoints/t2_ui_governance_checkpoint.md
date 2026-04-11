# T2 UI Governance Checkpoint

## Goal

Reduce the hotspot pressure around the T2 workbench without changing the external T2 behavior, request surface, or dump-state payload shape.

## What Changed

- Split demo execution and replay operations out of [ui.py](C:/AiUE/tools/t2/python/aiue_t2/ui.py) into [workbench_demo_ops.py](C:/AiUE/tools/t2/python/aiue_t2/workbench_demo_ops.py).
- Split rendering, selection, and explorer helpers out of [ui.py](C:/AiUE/tools/t2/python/aiue_t2/ui.py) into [workbench_render.py](C:/AiUE/tools/t2/python/aiue_t2/workbench_render.py).
- Kept `WorkbenchWindow` as the public entry point and preserved:
  - T2 native request controls
  - dump-state JSON shape
  - report tree and demo review behavior
  - existing pytest fixtures and process tests

## Structural Result

- [ui.py](C:/AiUE/tools/t2/python/aiue_t2/ui.py) reduced from the previous monolithic workbench controller to a smaller composition shell.
- Demo request/replay logic now has an explicit module boundary.
- Render/selection logic now has an explicit module boundary.

## Validation

- `pytest C:\\AiUE\\tests\\t2\\test_ui.py -q`
- `pytest C:\\AiUE\\tests\\t2\\test_process.py -q`
- `pytest C:\\AiUE\\tests\\t2 -q`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\\AiUE\\tools\\run_dynamic_balance.ps1`

## Why This Matters

This is a governance slice, not a feature slice. It lowers the cost of continuing the `E2` demo line while keeping room for future `Q5C-lite` and richer quality tooling without pushing more responsibilities back into a single hotspot file.
