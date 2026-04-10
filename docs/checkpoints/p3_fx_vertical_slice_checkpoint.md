# P3 FX Vertical Slice Checkpoint

## Summary

`P3` validates a third content axis on the generic slot platform: `fx`.

This first slice is intentionally minimal and controlled:

- host: `AiUEdemo`
- runtime path: generic slot application
- slot: `fx`
- item kind: `static_mesh`
- fixture asset: `/Game/Levels/LevelPrototyping/Meshes/SM_Cylinder.SM_Cylinder`
- attach target: `WeaponSocket`

The goal of `P3` is not to prove Niagara or time-based VFX behavior. It proves that AiUE can now carry a third slot axis on the same runtime path used by `weapon` and `clothing`, and that the result is inspectable and visually present.

## What P3 Proves

- `weapon` remains intact while a separate `fx` slot is added.
- The `fx` slot is resolved through generic slot bindings rather than a weapon-only side path.
- The managed `fx` component is a `StaticMeshComponent`.
- The managed `fx` component keeps a valid non-zero bounds payload.
- The `fx` slot can be tracked in visual proof output through `tracked_slots`.
- Both ready PMX bundles can carry the same `fx` proxy slot on the demo host.

## Scope

In scope:

- generic slot runtime
- demo host runtime inspection
- demo host visual proof
- evidence for `weapon + fx`

Out of scope:

- Niagara systems
- particle timing
- animated effect playback
- quality gates dedicated to FX semantics

## Residual Risk

`P3` uses a `static_mesh` proxy fixture, not a true effect system. This is deliberate.

The next meaningful step after `P3` is to decide whether `P4` should stay on generic coexistence/QA first, or whether there should be a later dedicated vertical slice for `niagara_system` as a new item kind.
