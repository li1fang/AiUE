# E2 Review History Checkpoint

## Summary

This checkpoint records the first `E2` slice where native review replay leaves behind a compact replay-history artifact instead of only the latest replay state.

`E2 review replay` already proved that bounded replay could be triggered from the review seam.
`E2 review history` proves that the same replay seam can now retain a small amount of recent operator memory in a machine-readable way.

## What Landed

- new latest artifact:
  - `Saved/demo/e2/latest/playable_demo_e2_review_history_state.json`
- new T2 dump-state fields:
  - `demo_review_history_state`
  - `demo_review_history_focus`
- the `Demo Review` view now surfaces:
  - compact history summary for the focused package
- new gate:
  - `playable_demo_e2_review_history`

## Verification

The implementation was verified through:

- `pytest C:\AiUE\tests\t2 -q`
  - `33 passed`
- real review-history gate:
  - `powershell -NoProfile -ExecutionPolicy Bypass -File C:\AiUE\run_playable_demo_e2_review_history.ps1 -WorkspaceConfig C:\AiUE\local\pipeline_workspace.local.json`
  - `status = pass`
  - `resolved_package_count = 2`
  - `history_focus_package_count = 2`
  - `passing_packages = 2`
  - `packages_with_two_kinds = 2`
  - `packages_with_min_events = 2`
- fresh native readback:
  - `T2 --latest --dump-state-json --exit-after-load`
  - `demo_review_history_state.status = pass`
  - `demo_review_history_focus.status = pass`

## Boundary

This checkpoint still does **not** add:

- a full replay-history browser
- side-by-side replay comparison
- packaged playable distribution
- generalized runtime authoring controls

It intentionally stops at:

1. compact replay-history retention
2. focused history readback per package
3. machine-readable recent-event evidence
4. a clean handoff point to either `E2G` or `Q5C-lite`
