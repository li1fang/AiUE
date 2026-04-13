# Motion Consumer Seam v0 Checkpoint

## Summary

This checkpoint records the first formal boundary for `toy-yard <-> AiUE` motion integration.

It exists because the current work is no longer blocked on "can a packet be exported."

The real question now is:

- what toy-yard must hand off
- what AiUE must consume
- how failures are assigned
- how results come back in a machine-readable way

## What This Checkpoint Adds

- `ADR-0011` proposing the motion consumer boundary
- a machine-readable consumer request schema
- a machine-readable consumer result schema
- concrete examples for both

The checkpoint does not claim motion is fully validated end to end.

Instead, it turns the next motion round from an implicit experiment into an explicit contract exercise.

For the next formal round:

- `import_motion_packet` is mandatory
- `animation_preview` is recommended when the consumer can advance that far
- `retarget_preflight` is optional and should not block `M0.5`

## Why Now

AiUE already has an emerging `import-motion-packet` implementation path.

That is precisely why the seam should be written down now rather than later:

- implementation is real enough to ground the API
- but still early enough that the boundary can be corrected cheaply

## Current Recommendation

Use this checkpoint as the basis for the next toy-yard coordination note.

Recommended message:

- align on seam v0 now
- continue shadow-consumer validation after alignment
- do not wait for "complete motion validation" before agreeing on ownership and result shape

## Attachment Set

Suggested artifacts to attach or link in the next cross-repo communication:

- `docs/adr/ADR-0011-motion-consumer-seam-v0.md`
- `docs/contracts/motion_consumer_request_v0.schema.json`
- `docs/contracts/motion_consumer_result_v0.schema.json`
- `docs/examples/motion_consumer_request_v0.example.json`
- `docs/examples/motion_consumer_result_v0.example.json`

## Non-Goals

This checkpoint does not:

- widen the stable `aiue.ps1` surface
- claim toy-yard should own Unreal import behavior
- replace the packet-side self-check already owned by toy-yard
- declare motion production-ready
