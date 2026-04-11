# E2 Session Roundtrip Checkpoint

## Summary

This checkpoint records the first `E2` slice where the Windows native workbench becomes capable of running a full session-level round instead of only isolated request invokes.

The key distinction is:

- `E2A credibility` proved that native-controlled single invokes are trustworthy
- `E2 session roundtrip` proves that the same native seam can now orchestrate the current full session bundle in one controlled pass

That turns `T2` from a native invoke surface into the first native session-round controller for `E2`.

## What Landed

- new latest artifact:
  - `Saved/demo/e2/latest/playable_demo_e2_round_state.json`
- new T2 dump-state fields:
  - `demo_round_control`
  - `demo_round_state`
- new T2 local control flag:
  - `--demo-session-round-invoke`
- the `Demo Request` view now provides:
  - `Invoke Session Round`
- new gate:
  - `playable_demo_e2_session_roundtrip`

## Verification

The implementation was verified through:

- `pytest C:\AiUE\tests\t2 -q`
  - `22 passed`
- real native session-round gate:
  - `powershell -NoProfile -ExecutionPolicy Bypass -File C:\AiUE\run_playable_demo_e2_session_roundtrip.ps1 -WorkspaceConfig C:\AiUE\local\pipeline_workspace.local.json`
  - `status = pass`
  - `resolved_package_count = 2`
  - `round_package_count = 2`
  - `invoke_count = 4`
  - `passing_packages = 2`
  - `action_motion_verified = 2`
  - `animation_pose_verified = 2`
- `T2 --latest --dump-state-json --exit-after-load` now exposes:
  - `demo_round_state.status = pass`
  - `demo_round_state.counts.package_count = 2`
  - `demo_round_control.status = pass`

## Boundary

This checkpoint still does **not** make `E2` a finished playable shell.

It deliberately stops short of:

- packaged desktop demo distribution
- generalized live session mutation inside UE
- broad operator controls outside the current `E2` request family
- richer playable loops with history, playlists, or runtime widgets

What it does add is the first session-level native control seam that is:

1. deterministic
2. evidence-backed
3. machine-readable
4. strong enough to serve as the next `E2` platform rung
