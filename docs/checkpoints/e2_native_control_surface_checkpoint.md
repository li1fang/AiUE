# E2 Native Control Surface Checkpoint

## Summary

This checkpoint records the first slice where the Windows native workbench stops being purely observational.

It still does **not** become a general operations console.

Instead, it grows one narrow, testable control seam:

- export the currently selected `E2` request
- dry-run the currently selected `E2` request
- expose the last control result through the same `dump-state-json` surface that tests already consume

That keeps the architecture honest:

- `T2` remains a native operator-facing tool
- the new capability is intentionally constrained
- the control result is now inspectable instead of disappearing into ad hoc shell history

## What Landed

- `T2` now tracks `demo_request_control`
- the `Demo Request` tab now shows:
  - workspace config path
  - export controls
  - dry-run controls
  - the latest control result JSON
- `run_t2_workbench.py` and `tools/run_t2_workbench.ps1` now accept:
  - `--workspace-config`
  - `--demo-request-export`
  - `--demo-request-dry-run`
  - `--demo-request-kind`
- `dump-state-json` now includes:
  - `demo_request_control.status`
  - `demo_request_control.operation`
  - `demo_request_control.request_kind`
  - `demo_request_control.workspace_config_path`
  - `demo_request_control.request_json_path`
  - `demo_request_control.result_json_path`
  - `demo_request_control.host_key`
  - `demo_request_control.errors`

## Verification

The implementation was verified through:

- `py_compile` on the updated `T2` app/UI/test modules
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\AiUE\tools\run_t2_workbench_tests.ps1 -SkipPrepareLatestPack -SkipSoak`
  - `13 passed, 1 deselected`
- fixture process smoke:
  - `run_t2_workbench.ps1 -Manifest <fixture> -SessionManifest <fixture_session> -DemoRequestExport -DemoRequestKind animation_preview -DumpStateJson -ExitAfterLoad`
  - `demo_request_control.status = pass`
  - `demo_request_control.operation = export`
- real-data native dry-run smoke:
  - `powershell -NoProfile -ExecutionPolicy Bypass -File C:\AiUE\tools\run_t2_workbench.ps1 -Latest -WorkspaceConfig C:\AiUE\local\pipeline_workspace.local.json -DemoRequestDryRun -DemoRequestKind animation_preview -DumpStateJson -ExitAfterLoad`
  - exit code `0`
  - `demo_request_control.status = pass`
  - `demo_request_control.operation = dry_run`
  - `demo_request_control.request_kind = animation_preview`
  - result artifact:
    - [animation_preview_dry_run_result.json](C:/AiUE/Saved/demo/e2/latest/requests/mingchao_sample_c0aeb7ff_character_35215ba5/animation_preview/MM_Attack_01/animation_preview_dry_run_result.json)
  - result summary:
    - `status = pass`
    - `command = animation-preview`
    - `result.status = pass`
    - warning retained:
      - `animation_blueprint_library_unavailable`

## Boundary

This checkpoint still does **not** claim that `E2` is feature-complete.

It deliberately stops short of:

- a full in-app launch lifecycle
- session switching commands that mutate a live UE runtime
- packaged playable UI
- generalized execution controls for every host command

What it does add is the first native control layer that is:

1. constrained
2. stateful
3. testable
4. readable through automation

That is exactly the kind of small, durable step the `E2` line needs.
