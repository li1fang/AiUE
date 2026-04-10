# D12 Cross-Bundle Demo Checkpoint

## Scope

`D12` validates that the demo retarget-preview stack is reusable across more than one ready PMX character bundle.

Instead of only proving the path on the first validated character, `D12` reruns the same demo-side milestone chain on the second ready bundle.

## Bundle Coverage

Primary bundle already validated before `D12`:

- `mingchao_sample_c0aeb7ff_character_35215ba5`

Second ready bundle exercised by `D12`:

- `mingchao_xjqy8yn4h6_b6e33424_character_f91ab5d6`

## Pipeline Reused

`D12` drives the second bundle through the same fixed chain:

- `D4` retarget preflight
- `D5` retarget bootstrap
- `D7` chain refinement
- `D8` single-animation retarget preview
- `D10` mixed-family regression
- `D11` repeated-run stability regression

## Main Outcome

The second ready bundle reached `D11 pass` without requiring a separate one-off workflow.

That means the current demo stack now has evidence for:

- retarget viability across two PMX characters
- mixed-family preview on two PMX characters
- repeated-run stability on two PMX characters

The latest report is:

- `Saved/verification/latest_demo_cross_bundle_regression_d12_report.json`

## What Passed

- all `6` required pipeline steps passed
- the second bundle passed:
  - `idle`
  - `attack`
  - `jog`
  - `walk`
- the second bundle also passed the repeated-run `D11` stability gate
- resolved animation outputs and retarget asset paths stayed stable across repeated runs

## Residual Quality Note

One of the second-bundle `walk_forward` side shots emitted a framing-related warning:

- `subject_not_visible_in_camera_plan`

The case still passed because actual screenshot evidence and external motion evidence remained valid.

So the stack is working, but shot-quality enforcement is still softer than it should be.

## Recommended Next Step

The most useful next move is no longer “can another bundle pass”.

It is:

- add a stricter shot-quality / subject-visibility gate
- make framing warnings first-class quality signals
- only after that scale wider across more bundles or content classes
