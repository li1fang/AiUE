# Q2 Demo Composition Quality Checkpoint

## Scope

`Q2` builds directly on `Q1`.

It does not revisit import, retarget, or animation execution. Instead, it asks a tighter presentation question:

- is the subject framed consistently enough
- and is the weapon visible often enough

to treat the current demo line as a credible preview surface rather than just a technically passing motion surface.

## Main Outcome

`Q2` adds a stricter composition/weapon-quality gate on top of the refreshed `D12` cross-bundle line and the `Q1` subject-visibility prerequisite.

The latest report is:

- `Saved/verification/latest_demo_composition_quality_gate_q2_report.json`

This line currently passes with:

- `2` passing rounds
- `8` passing cases
- `16` passing shot pairs
- `32` passing phase shots
- `16` weapon-visible shot pairs
- `20` weapon-visible phases

## What Q2 Checks

For every evaluated case and shot pair, `Q2` enforces:

- minimum left/right subject margin
- minimum top subject margin
- bounded horizontal subject-center offset
- bounded before/after subject-center drift
- bounded before/after subject-coverage drift
- weapon visibility in enough phases and enough distinct shot pairs

`Q2` is stricter than `Q1`, but it still reflects the current stage of the pipeline:

- subject framing must be stable in every phase
- weapon visibility is enforced at case level rather than requiring every single after-shot to keep the weapon fully visible

## Why This Layer Exists

`Q1` proves that the subject is present, in frame, unobstructed, and no longer affected by false-positive camera-plan warnings.

`Q2` moves one layer higher:

- it treats framing consistency as a first-class quality signal
- it treats weapon visibility as a reusable demo-quality requirement

This is the point where the demo stack starts looking like a real preview surface instead of only a motion-verification rig.

## Recommended Next Step

If `Q2` passes, the next useful move is:

- scale `Q2` to more ready bundles
- or add a `Q3` layer for stronger composition semantics, such as tighter weapon prominence or shot-family-specific framing profiles

If `Q2` fails, the next useful move is not more gate work.

It is:

- adjust demo shot plans or camera presets until weapon visibility and framing stabilize under the new bar
