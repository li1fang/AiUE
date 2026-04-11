# E2 Demo Request Surface Checkpoint

## Summary

This checkpoint records the first slice where `T2` no longer stops at reading the `E2` session manifest.

It now derives concrete demo host-command payloads from the current native selection state.

That means the repo now has three stacked `E2` layers:

1. session manifest generation
2. native session exploration
3. native request lowering

## What Landed

- `T2` state now derives:
  - `demo_request.requests.action_preview`
  - `demo_request.requests.animation_preview`
- both requests are lowered from:
  - selected package
  - selected action preset
  - selected animation preset
  - current session host/level/spawn/shot data
  - current clothing / fx slot binding overrides
- `T2` UI now has a dedicated `Demo Request` tab that shows the current lowered JSON

## Verification

The implementation was verified through:

- `py_compile` on the updated `T2` state/UI/test modules
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\AiUE\tools\run_t2_workbench_tests.ps1 -SkipPrepareLatestPack -SkipSoak`
  - `8 passed, 1 deselected`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\AiUE\tools\run_t2_workbench.ps1 -Latest -DumpStateJson -ExitAfterLoad`
  - `status = pass`
  - `demo_request.status = pass`
  - `demo_request.request_kinds = [action_preview, animation_preview]`
  - `demo_request.requests.action_preview.command = action-preview`
  - `demo_request.requests.animation_preview.command = animation-preview`

## Boundary

This checkpoint still does **not** execute UE commands.

It adds a controlled request surface, not a launch button.

That boundary is deliberate:

- request generation can now be tested and reviewed in isolation
- the next `E2` slice can choose an execution path without first re-deriving payload shape inside the UI layer
