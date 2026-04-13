# M2 Motion Fixture Diversity Checkpoint

## Summary

`M2` is the first motion node that asks a diversity question instead of a single-fixture question.

It does not invent a new motion execution path.

It reuses the existing `M0.5` consumer chain, but runs it across every ready package in the curated diversity export.

## Fixed Scope

Current `M2` scope is tied to:

- `trial-motion-m2-diversity`

Current curated package set:

- `pkg_route-a-3s-turn-hand-ready-v0-2_a70fed1ad7`
- `pkg_route-a-3s-two-hand-receive-ready-v0-2_4654f004ac`
- `pkg_route-a-3s-half-turn-present-ready-v0-2_5b37783497`

## Pass Conditions

`M2` passes only if every curated package satisfies:

- `M0.5 gate status = pass`
- `consumer_result.status = pass`
- `owner = none`
- `subject_visible = true`
- `pose_changed = true`

And the executed package/scenario set must still match the curated diversity profile.

## Why This Node Matters

This is the first real answer to the question:

`Is the current motion seam real beyond one lucky sample?`

If `M2` passes, the motion line is no longer only a controlled single-fixture success.

It becomes a small but real multi-scenario capability.
