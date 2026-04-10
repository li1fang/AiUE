# Q4 Multi-Slot Quality Checkpoint

## Summary

`Q4` is the first slot-aware quality gate built on top of `P4`.

It does not prove new runtime capability. It proves that the existing multi-slot platform is producing outputs that are strong enough to trust at a higher quality bar:

- `weapon`
- `clothing`
- `fx`

## What Q4 Checks

- `front` and `side` are treated as strict shots.
- In each strict shot:
  - the shot itself must pass
  - `weapon` must remain visible above a minimum threshold
  - `clothing` must remain visible above a minimum threshold
  - `fx` must remain visible above a minimum threshold
- Each package must also have at least one stronger `hero shot` where all three slot axes exceed higher coexistence thresholds together.

## Why This Exists

`P4` proves coexistence.

`Q4` proves usable coexistence quality.

That distinction matters because a platform can technically carry three slots at once while still producing weak or inconsistent demo evidence. `Q4` makes that harder to hide.

## Current Caveat

One ready bundle still uses `owner_origin` fallback for the clothing slot. `Q4` currently allows that only because:

- the clothing component remains valid
- the clothing component remains visually present
- the stricter `front/side` thresholds still pass
