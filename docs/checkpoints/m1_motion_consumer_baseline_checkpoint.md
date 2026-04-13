# M1 Motion Consumer Baseline Checkpoint

## Summary

`M1` is the first stability node after `M0.5`.

`M0.5` proved that the motion seam can close once.

`M1` answers the next, stricter question:

`Can the same controlled toy-yard motion packet be consumed and previewed repeatedly without ownership drift or credibility loss?`

This checkpoint keeps the scope intentionally narrow:

- same controlled trial fixture
- same controlled package family
- same `M0.5` consumer path
- repeated execution instead of feature expansion

## Fixed Shape

`M1` does not introduce a parallel motion implementation.

It reruns the existing:

- `motion_shadow_packet_trial_m0_5`

Default shape:

- iterations: `3`
- package: `pkg_route-a-3s-turn-hand-ready-v0-2_a70fed1ad7`
- sample: `sample_route-a-3s-turn-hand-ready_797943f40a`

## Pass Conditions

`M1` passes only when every rerun iteration satisfies all of these:

- `M0.5 gate status = pass`
- `consumer_result.status = pass`
- `communication_signal.owner = none`
- `preview_evidence.subject_visible = true`
- `preview_evidence.pose_changed = true`

## Why This Node Exists

This node is valuable because it tests the right thing for the current stage:

- not broader fixture diversity yet
- not richer motion semantics yet
- not default-source graduation yet

It simply checks whether the current controlled baseline is repeatable enough to trust as a foundation.

## Upgrade Meaning

If `M1` passes, the motion line has crossed from:

- `seam can close once`

to:

- `controlled baseline can be rerun and still stay credible`

That is the correct prerequisite for:

- `M1.5 result-import readiness`
- `M2 fixture diversity`
