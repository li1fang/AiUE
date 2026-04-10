# Q1 Demo Shot Quality Checkpoint

## Scope

`Q1` does not expand the demo-animation stack.

It tightens the quality bar on top of the existing `D12` cross-bundle regression line by separating:

- camera-plan estimates
- actual post-capture shot evidence

The purpose of `Q1` is to stop treating `subject_not_visible_in_camera_plan` as a trustworthy failure signal when the rendered shot itself proves the subject is visible and unobstructed.

## Main Outcome

`Q1` introduces a dedicated shot-quality gate and reruns the active `D12` source line with reconciled host-side shot reporting.

The latest passing report is:

- `Saved/verification/latest_demo_shot_quality_gate_q1_report.json`

The refreshed `D12` source report is:

- `Saved/verification/latest_demo_cross_bundle_regression_d12_report.json`

## What Changed

- host-side shot reporting now records a `quality_gate` block derived from:
  - `subject_coverage`
  - `weapon_coverage`
  - `line_of_sight`
  - `output_exists`
- host-side capture now records `camera_plan_assessment`
- `subject_not_visible_in_camera_plan` is reconciled against post-capture evidence instead of remaining as an unconditional warning
- `Q1` evaluates every `before/after` phase shot from the current `D11/D12` line

## What Passed

- `2` evaluated rounds passed
- `8` evaluated cases passed
- `16` evaluated shot pairs passed
- `32` evaluated phase shots passed
- retained `subject_not_visible_in_camera_plan` warnings: `0`
- below-threshold subject shots: `0`
- line-of-sight failures: `0`
- missing-image failures: `0`

## Why This Matters

Before `Q1`, the demo stack could pass while still carrying misleading framing warnings that were only based on camera-plan estimation.

After `Q1`, shot quality is judged from real capture evidence, and the cross-bundle demo line has explicit proof that:

- the subject is in frame
- the subject center remains in frame
- line of sight is clear
- the image artifact exists
- the old camera-plan warning no longer leaks into otherwise valid shots

## Recommended Next Step

The next useful move is no longer generic framing cleanup.

It is either:

- extend the same quality gate to more ready bundles
- or add a stricter weapon/composition quality layer on top of `Q1`

The current cross-bundle demo line is now strong enough that future work should focus on scaling or sharpening quality, not on re-proving the same warning cleanup.
