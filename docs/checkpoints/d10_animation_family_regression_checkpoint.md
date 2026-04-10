# D10 Animation Family Regression Checkpoint

## Scope

`D10` extends the passing `D8` and `D9` retarget-preview path into a mixed motion-family regression on the demo host.

This gate stays intentionally narrow:

- one ready PMX bundle
- one demo host
- fixed cameras
- three motion families:
  - `idle`
  - `attack`
  - `locomotion`

## Fixed Cases

The current fixed `D10` set is:

- `idle`: `/Game/CombatMagicAnims/Demo/Mannequins/Anims/Unarmed/MM_Idle`
- `attack`: `/Game/CombatMagicAnims/Demo/Mannequins/Anims/Unarmed/Attack/MM_Attack_01`
- `locomotion`: `/Game/CombatMagicAnims/Demo/Mannequins/Anims/Unarmed/Jog/MF_Unarmed_Jog_Fwd`

## Main Outcome

`D10` proves that the current preview stack is not limited to one attack-only example.

For the same PMX character bundle, AiUE can now:

- retarget demo animations from more than one motion family
- apply the retargeted result on the demo host
- capture before/after screenshots
- produce engine-side motion proof
- produce external cropped-image motion proof

The latest report is:

- `Saved/verification/latest_demo_animation_family_regression_d10_report.json`

## What Passed

- all `3` requested cases resolved and passed
- all `3` motion families passed
- all `3` cases produced engine-side motion evidence
- all `3` cases produced external motion evidence
- total captured shot pairs: `6`

## Why This Matters

This is the first point where the system demonstrates a small but real motion-family spread:

- stationary loop content
- explicit combat action content
- forward locomotion content

That makes the current preview stack much more credible as a reusable automation substrate instead of a single hand-tuned animation demo.

## Recommended Next Step

`D11` should stay focused on stability, not breadth:

- keep the same PMX bundle first
- add one more locomotion-adjacent case such as walk or jump
- check whether cached retarget outputs remain stable across repeated runs
- only then consider expanding to a second PMX bundle
