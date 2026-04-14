# ADR-0014: Canonical Fusion Fixture Handoff v0

## Status

Accepted

## Context

`C1` gives AiUE a narrow parametric body contract, but it still does not define what the first real Houdini artifact must look like.

The repo needs a first qualified handoff target that is:

- narrow enough for the first real sample
- strict enough to support Linux automation later
- explicit enough that `Houdini -> AiUE` does not become another oral tradition

The current first real sample is a single zipped high-resolution mesh module representing:

- waist
- hips
- upper thighs

This is not yet a runtime-ready avatar.
It is the first candidate `C2` body-platform artifact.

## Decision

AiUE adopts a `Canonical Fusion Fixture Handoff v0`.

`C2` is defined as:

- an offline DCC handoff checkpoint
- centered on a machine-readable Houdini export package
- validated by AiUE as a body-platform report
- not yet equivalent to `C4` runtime body proof

### First-Pass Scope

The first accepted scope is:

- `fixture_scope = lower_body_core`

This allows the repo to qualify the first fused lower-body module before attempting a full fused body.

### First-Pass Delivery Package

A qualified `C2` handoff package must contain:

- one primary mesh artifact
- one manifest
- explicit exporter metadata
- explicit coordinate metadata
- source module lineage
- fusion recipe identity

The package may omit final runtime materials or textures in the first pass, but it must state that clearly in the manifest.

### Required Manifest Semantics

The manifest must identify:

- `fixture_id`
- `body_family_id`
- `fixture_scope`
- `source_module_ids`
- `primary_mesh_relative_path`
- `fusion_recipe_id`
- `rig_profile_id`
- `material_profile_id`
- `exporter.tool = houdini`
- `coordinate_system.linear_unit = cm`
- `coordinate_system.up_axis = z`

### Boundary

`Houdini` owns:

- offline fusion recipe execution
- seam cleanup
- mesh cleanup
- material/UV handoff metadata
- batch export preparation

`AiUE` owns:

- handoff validation
- report generation
- later runtime consumption
- later quality and demo evidence

## Consequences

Positive:

- gives the first Houdini artifact a real contract
- makes Linux automation easier because recipe identity and coordinates are explicit
- keeps C2 narrow and reproducible

Tradeoffs:

- a raw FBX zip by itself is no longer considered a qualified C2 artifact
- the first C2 pass is deliberately narrower than the eventual full fused avatar target

## Follow-Up

Immediate follow-up:

- land `run_canonical_fusion_fixture_c2.py`
- add a manifest template for the first Houdini handoff
- qualify the first lower-body core sample

Later follow-up:

- expand from `lower_body_core` to a canonical fused full-body fixture
- feed the result into `C3 Skeletal Transfer Proof`
