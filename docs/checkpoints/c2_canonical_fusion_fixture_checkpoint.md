# C2 Canonical Fusion Fixture Checkpoint

## Goal

`C2` is the first offline body-fusion handoff checkpoint.

It does not prove:

- runtime body assembly
- rig transfer quality
- soft-tissue behavior

It proves a narrower but critical thing:

`Can Houdini hand AiUE a machine-readable, replayable, lineage-aware fusion artifact that is clean enough to become the canonical next input?`

## First Fixture

The first accepted fixture is intentionally narrow:

- `fixture_scope = lower_body_core`
- content focus:
  - waist
  - hips
  - upper thighs

That is enough to prove the seam and automation contract before the line expands to a full fused body.

## Required Delivery Shape

The first qualified package must include:

- one primary mesh
- one manifest
- explicit source module lineage
- explicit coordinate metadata
- explicit exporter metadata
- explicit fusion recipe identity

The first package may still be:

- high resolution
- not runtime-ready
- not fully textured

But it must not be:

- anonymous
- axis-ambiguous
- recipe-ambiguous
- lineage-free

## AiUE Validation Expectations

`run_canonical_fusion_fixture_c2.py` checks:

- manifest presence
- primary mesh resolvability
- `fixture_scope`
- `body_family_id`
- `source_module_ids`
- `exporter.tool = houdini`
- `coordinate_system.linear_unit = cm`
- `coordinate_system.up_axis = z`
- `fusion_recipe_id`

## Why This Node Exists

Without `C2`, the body line would jump from contract theory straight into:

- ad hoc DCC experiments
- unnamed FBX exports
- hard-to-replay Linux jobs
- later rig/runtime work with no stable fused truth artifact

With `C2`, the repo gains:

- a first real Houdini handoff contract
- a reportable body artifact
- a stable input to `C3`

## Next Node

If `C2` is green for the first qualified fixture, the next node is:

- `C3 Skeletal Transfer Proof`
