# E2 Controlled Request Runner Checkpoint

## Summary

This checkpoint records the first `E2` slice where the native request surface becomes executable through a repo-local tooling runner.

The intent is to keep one clean separation:

- `T2` still owns read-only session and request inspection
- the new runner owns controlled request export and invocation

That gives the playable-demo line a testable execution seam without forcing the Windows workbench to become an operation-heavy UI too early.

## What Landed

- new repo-local runner:
  - `tools/run_e2_demo_request.ps1`
- new Python entrypoint:
  - `tools/t2/python/run_e2_demo_request.py`
- new request-runner module:
  - `tools/t2/python/aiue_t2/demo_request_runner.py`
- the runner can:
  - resolve the current request from `--latest` or an explicit manifest
  - select `action_preview` or `animation_preview`
  - dump the resolved request JSON
  - write the request JSON to a file
  - invoke the request through the existing host bridge
  - invoke the same path with `--dry-run` for controlled smoke verification

## Verification

The implementation was verified through:

- `py_compile` on:
  - `tools/t2/python/aiue_t2/demo_request_runner.py`
  - `tools/t2/python/run_e2_demo_request.py`
  - `tests/t2/test_demo_request_runner.py`
  - `tests/t2/helpers.py`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\AiUE\tools\run_t2_workbench_tests.ps1 -SkipPrepareLatestPack -SkipSoak`
  - `11 passed, 1 deselected`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\AiUE\tools\run_e2_demo_request.ps1 -Latest -RequestKind action_preview -DumpRequestJson`
  - `status = pass`
  - `request_kind = action_preview`
  - `request_payload.command = action-preview`
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\AiUE\tools\run_e2_demo_request.ps1 -Latest -RequestKind action_preview -WorkspaceConfig C:\AiUE\local\pipeline_workspace.local.json -DryRun -ResultJsonPath C:\AiUE\Saved\demo\e2\latest\requests\latest_action_preview_dry_run_result.json -DumpRequestJson`
  - `status = pass`
  - `invoke.status = pass`
  - `invoke.dry_run = true`
  - `request_payload.host_key = demo`

## Boundary

This checkpoint still does **not** make `T2` an operations console.

It deliberately stops short of:

- adding a launch button to the Windows native workbench
- owning a longer-lived playable session loop
- claiming the repo now has a full interactive playable shell

What it does add is the first controlled execution seam for `E2`, which is exactly the right bridge between:

1. native session inspection
2. native request lowering
3. future interactive demo control
