# E1 Stability Checkpoint

## Summary

This checkpoint records that `E1` has moved from:

- a first passing showcase gate

to:

- a stable demo entry milestone for `E2`

The stability proof is now explicit and reproducible through:

- [latest_showcase_demo_e1_stability_report.json](C:/AiUE/Saved/verification/latest_showcase_demo_e1_stability_report.json)

## What Was Verified

The internal `showcase_demo_e1_stability` gate now checks:

1. `E1` rerun `01`
2. `E1` rerun `02`
3. `T1` latest evidence-pack refresh
4. `T2 --latest --dump-state-json --exit-after-load`

The gate requires:

- `2` consecutive `E1` passes
- matching rerun signatures across:
  - resolved package ids
  - package counts
  - image counts
  - hero-shot counts
  - motion-pass counts
- refreshed `T1` latest manifest
- `T2` latest state to return `status = pass`
- `T2` latest active-line list to include `showcase_demo_e1`

## Current Result

Latest status:

- `showcase_demo_e1 = pass`
- `showcase_demo_e1_stability = pass`
- `stable reruns = 2 / 2`
- `T1 refresh = pass`
- `T2 latest consumption = pass`

Latest stable counts:

- `required_package_count = 2`
- `passing_packages = 2`
- `captured_before_images = 6`
- `captured_after_images = 6`
- `hero_shots_passed = 2`
- `motion_pass_shots = 6`

## Consequence

The original `E2` entry condition from [ADR-0005-demo-capability-line.md](C:/AiUE/docs/adr/ADR-0005-demo-capability-line.md) is now satisfied.

That does **not** mean playable-demo work must start immediately.
It means the repo now has a clean, evidence-backed point where `E2` can be opened as a dedicated work item without bypassing the demo proof ladder.

## Recommended Next Move

The sensible next move is:

1. keep `E1` as the evidence-first stable milestone
2. decide whether the next work item should be:
   - `E2 playable demo`, or
   - a more targeted tool / quality increment that clearly improves demo confidence

The one move to avoid is blending playable demo work back into `E1` without a separate scope boundary.
