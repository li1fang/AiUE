# M0.5 Motion Shadow Packet Trial Checkpoint

## Summary

This checkpoint is the first AiUE-side implementation node after the producer/consumer boundary was clarified for motion.

`M0.5` is not a "motion is now fully green" checkpoint.

It is a seam checkpoint.

The point is to prove three things:

- AiUE can consume the toy-yard motion packet without raw folder discovery or toy-yard SQLite
- AiUE can write a machine-readable `motion_consumer_request_v0` and `motion_consumer_result_v0`
- failures can be routed to `toy-yard`, `aiue`, or `none` without ambiguity

## Fixed Scope

The first controlled trial remains locked to:

- profile: `trial-motion-turn-hand-ready`
- sample: `sample_route-a-3s-turn-hand-ready_797943f40a`
- preferred package: `pkg_route-a-3s-turn-hand-ready-v0-2_a70fed1ad7`

The runner first attempts:

1. `import-motion-packet`
2. `retarget-bootstrap` when import succeeds
3. `retarget-author-chains` when bootstrap evidence shows source chains are still missing
4. `animation-preview` after the retarget inputs are ready

## Important Interpretation

`M0.5` runner `status = pass` means the seam closed.

That means:

- packet selection succeeded
- request/result artifacts were written
- ownership routing is explicit

It does not require the first animation preview to be green.

The underlying consumer execution still has its own result:

- `consumer_result.status = pass | fail`

This split is deliberate because the value of `M0.5` is learning whether the handoff contract and ownership routing are stable, not pretending the whole motion lane is already mature.

## Current State

The current AiUE latest proof has already crossed the stronger interpretation:

- `consumer_result.status = pass`
- `communication_signal.owner = none`
- `preview_evidence.subject_visible = true`
- `preview_evidence.pose_changed = true`
- `consumer_result.warnings = []`

That means `M0.5` is still the seam node, but the controlled fixture is now good enough to act as the baseline for `M1 Motion Consumer Baseline`.

## Artifacts

The AiUE runner writes:

- `motion_consumer_request_v0.json`
- `motion_consumer_result_v0.json`
- `motion_consumer_context.json`
- `motion_consumer_state.json`
- `latest_motion_shadow_packet_trial_m0_5_report.json`

These are the intended result-import surfaces for toy-yard.

## Upgrade Rule

This checkpoint only upgrades toward `M1 Default Source` when:

- `consumer_result.status = pass`
- `communication_signal.owner = none`

Until then, `M0.5` remains the correct node.
