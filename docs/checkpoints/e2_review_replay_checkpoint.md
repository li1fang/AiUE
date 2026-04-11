# E2 Review Replay Checkpoint

## Summary

This checkpoint records the first `E2` slice where the native review layer can trigger bounded replay directly from the review tab.

`E2 review navigation` already proved that review evidence could be focused package-by-package.
`E2 review replay` proves that the same focused review seam can now launch a constrained replay loop and persist replay-specific state.

## What Landed

- new latest artifact:
  - `Saved/demo/e2/latest/playable_demo_e2_review_replay_state.json`
- new T2 dump-state fields:
  - `demo_review_replay_state`
  - `demo_review_replay_control`
- new native review actions:
  - `Replay Action`
  - `Replay Animation`
- new local T2 flag:
  - `--demo-review-replay`
- new gate:
  - `playable_demo_e2_review_replay`

## Verification

The implementation was verified through:

- `pytest C:\AiUE\tests\t2 -q`
  - `30 passed`
- real review-replay gate:
  - `powershell -NoProfile -ExecutionPolicy Bypass -File C:\AiUE\run_playable_demo_e2_review_replay.ps1 -WorkspaceConfig C:\AiUE\local\pipeline_workspace.local.json`
  - `status = pass`
  - `resolved_package_count = 2`
  - `replayed_package_count = 2`
  - `replay_invoke_count = 4`
  - `passing_packages = 2`
  - `action_replay_verified = 2`
  - `animation_replay_verified = 2`
  - `fresh_readback_passed = 2`
- fresh native readback:
  - `T2 --latest --dump-state-json --exit-after-load`
  - `demo_review_replay_state.status = pass`
  - replay state still contains both current packages and both replay kinds

## Boundary

This checkpoint still does **not** add:

- replay history browsing across multiple rounds
- richer session playlists
- packaged playable distribution
- generalized runtime authoring controls

It intentionally stops at:

1. focused review replay
2. replay-specific latest artifact persistence
3. fresh native readback after replay
4. a stronger base for the next `E2` slice
