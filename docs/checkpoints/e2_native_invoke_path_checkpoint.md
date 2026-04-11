# E2 Native Invoke Path Checkpoint

## Summary

This checkpoint records the slice where the Windows native workbench grows from:

- export
- dry-run

into:

- export
- dry-run
- invoke

That sounds small, but it changes the shape of `E2` quite a bit.

The workbench is no longer only a read surface with a simulated execution seam.
It now has a cautious real execution path, while still keeping the boundary intentionally narrow and machine-readable.

## What Landed

- `T2` now provides:
  - `Invoke Action Request`
  - `Invoke Animation Request`
- `run_t2_workbench.py` and `tools/run_t2_workbench.ps1` now accept:
  - `--demo-request-invoke`
- `demo_request_control` now includes:
  - `dry_run`
  - `result_status`
  - `invocation_returncode`
- the invoke path reuses the existing repo-local runner and host bridge rather than inventing a second execution mechanism

## Verification

The implementation was verified through:

- `py_compile` on the updated `T2` app/UI/test modules
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\AiUE\tools\run_t2_workbench_tests.ps1 -SkipPrepareLatestPack -SkipSoak`
  - `13 passed, 1 deselected`
- widget-level mocked control test:
  - `Invoke Action Request` updates `demo_request_control.operation = invoke`
  - `demo_request_control.dry_run = false`
  - `demo_request_control.host_key = demo`
- real-data native invoke smoke:
  - `powershell -NoProfile -ExecutionPolicy Bypass -File C:\AiUE\tools\run_t2_workbench.ps1 -Latest -WorkspaceConfig C:\AiUE\local\pipeline_workspace.local.json -DemoRequestInvoke -DemoRequestKind action_preview -DumpStateJson -ExitAfterLoad`
  - exit code `0`
  - `demo_request_control.status = pass`
  - `demo_request_control.operation = invoke`
  - `demo_request_control.request_kind = action_preview`
  - `demo_request_control.result_status = pass`
  - `demo_request_control.invocation_returncode = 0`
  - result artifact:
    - [action_preview_invoke_result.json](C:/AiUE/Saved/demo/e2/latest/requests/mingchao_sample_c0aeb7ff_character_35215ba5/action_preview/showcase_root_translate_and_turn/action_preview_invoke_result.json)
  - real output evidence confirms:
    - `command = action-preview`
    - `result.status = pass`
    - before/after captures exist under:
      - [before](C:/AiUE/Saved/demo/e2/latest/requests/mingchao_sample_c0aeb7ff_character_35215ba5/action_preview/showcase_root_translate_and_turn/before)
      - [after](C:/AiUE/Saved/demo/e2/latest/requests/mingchao_sample_c0aeb7ff_character_35215ba5/action_preview/showcase_root_translate_and_turn/after)
    - tracked slot coverage remains present for:
      - `clothing`
      - `fx`

## Boundary

This checkpoint still does **not** make `T2` a full playable shell.

It deliberately stops short of:

- long-lived session orchestration
- generalized host-command execution
- runtime package switching in a live session
- packaged playable UI

What it does add is the first native invoke path that is:

1. constrained
2. stateful
3. automatable
4. backed by real output artifacts

That is exactly the right next rung for the current `E2` line.
