# Q3 Demo Semantic Framing Checkpoint

## Scope

`Q3` sits on top of `Q1` and `Q2`.

It does not ask only whether the subject is visible or whether the framing is stable.

It asks whether each shot family now behaves like an intentional demo shot:

- `front` should place the subject in a front-facing showcase lane
- `side` should place the subject in a side-profile showcase lane
- visible weapon evidence should also appear on the expected side of the subject for that shot family

## Main Outcome

`Q3` adds shot-family-specific semantic framing profiles and weapon-position checks on top of the existing cross-bundle demo line.

The latest report is:

- `Saved/verification/latest_demo_semantic_framing_gate_q3_report.json`

This line currently passes with:

- `2` passing rounds
- `8` passing cases
- `16` passing shot pairs
- `16` semantic weapon pairs
- `8` passing `front` semantic pairs
- `8` passing `side` semantic pairs

## What Q3 Checks

For each `front` and `side` shot pair, `Q3` enforces:

- a shot-family-specific subject center band
- a shot-family-specific subject edge or margin rule
- a minimum weapon prominence threshold for that shot family
- a semantic weapon position rule:
  - `front`: visible weapon evidence must sit left of subject center
  - `side`: visible weapon evidence must sit right of subject center

## Why This Matters

`Q1` proves the subject is real and unobstructed.

`Q2` proves the framing is stable and the weapon is visible often enough.

`Q3` is the first layer that starts treating the demo output as a designed presentation surface instead of a generic capture rig.

It encodes the intent of the current `front/side` camera families directly into a reusable gate.

## Recommended Next Step

If `Q3` passes, the next useful move is:

- scale the same semantic framing gate to more ready bundles
- or introduce a `Q4` layer for shot-family-specific animation semantics, such as stronger attack readability or locomotion silhouette checks

If `Q3` fails, the next useful move is not more gate complexity.

It is:

- adjust camera presets or shot planning until the intended `front/side` presentation language becomes stable enough to satisfy the gate
