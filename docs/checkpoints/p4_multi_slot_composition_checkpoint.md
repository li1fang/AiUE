# P4 Multi-Slot Composition Checkpoint

## Summary

`P4` is the first gate that validates true multi-slot coexistence on a single host:

- `weapon`
- `clothing`
- `fx`

It does not add new runtime item kinds. It proves that the current generic slot platform can keep three slot axes alive at the same time without collapsing back into a weapon-only path.

## What P4 Proves

- The base `weapon` slot stays intact under additional slot pressure.
- A `clothing` slot and an `fx` slot can be applied together on the same host.
- `inspect-slot-runtime` can resolve all three slots together.
- `inspect-host-visual` can track both non-weapon slots in the same capture run.
- At least one visual shot per package shows `weapon + clothing + fx` together with sufficient evidence.

## Scope

In scope:

- generic slot coexistence
- multi-slot runtime evidence
- multi-slot visual evidence
- first slot-aware QA expansion for co-presence

Out of scope:

- Niagara-specific runtime
- semantic FX quality
- clothing semantics beyond attachment and visibility
- reference-image QA

## Residual Risk

The same clothing caveat from `P2` still exists: one ready bundle may fall back to `owner_origin` instead of a true head-like attach target. `P4` accepts that only when the clothing component remains valid and visually present.

The `fx` axis still uses a `static_mesh` proxy, not a real effect system. This is intentional. `P4` is about coexistence first, not final FX semantics.
