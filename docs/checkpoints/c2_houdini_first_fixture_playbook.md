# C2 Houdini First Fixture Playbook

This playbook now has a narrower, more practical goal:

`produce a provider-ready source handoff that can later become BodyPaint's upstream input`

## First Real Sample

Current sample:

- [scan-model-hi.zip](C:/Users/garro/Downloads/scan-model-hi.zip)

Current observed shape:

- one zipped `FBX`
- no manifest
- no recipe metadata
- no coordinate metadata
- no lineage metadata

This means the sample is already a useful raw source drop, but it is **not yet** a qualified `C2` handoff package.

It is also not yet a `provider-ready source handoff`.

## What "Provider-Ready" Means

At this stage, the target is not the final downstream `C2` deliverable.

The current target is smaller:

- AiUE can validate the package shape
- AiUE can derive a provider JSON
- the provider reports:
  - `status = ready`
  - `consumer_hints.ready_for_bodypaint = true`

That is enough for BodyPaint to begin real consumer-side integration.

## First Qualified Target

The first qualified `C2` output should remain narrow:

- `fixture_scope = lower_body_core`
- one primary fused lower-body mesh
- explicit Houdini recipe identity
- explicit `cm + z-up` export metadata
- explicit source module lineage

The goal is not “perfect art”.
The goal is “clean first contract”.

## Recommended Houdini Flow

### 1. Ingest

- import the raw `FBX`
- preserve the untouched original in a locked reference branch
- create a working branch for cleanup and export preparation

### 2. Normalize

- isolate the intended lower-body shell
- remove obvious junk pieces, duplicate shells, and accidental detached fragments
- keep this step conservative; do not start sculpting or artistic redesign

### 3. Establish Export Convention

The first package should be exported with:

- UE-facing centimeter metadata
- explicit `z-up`
- one chosen forward axis that is written into the manifest
- one deterministic output mesh path

Do not rely on memory for this.
Write it into the package.

### 4. Freeze First Fixture Scope

For the first pass, do not try to solve:

- head join
- bust replacement
- final leg-length variation
- runtime modular swapping

The first fixture should only answer:

- can this lower-body core become a stable canonical fused module?

### 5. Write the Manifest

The first package should ship with:

- [canonical_fusion_fixture_manifest.example.json](C:/AiUE/examples/body_platform/canonical_fusion_fixture_manifest.example.json)
- [canonical_fusion_fixture_manifest.v0.schema.json](C:/AiUE/schemas/canonical_fusion_fixture_manifest.v0.schema.json)
- [c2_provider_ready_source_handoff_checklist.md](C:/AiUE/docs/checkpoints/c2_provider_ready_source_handoff_checklist.md)

At minimum, fill:

- `fixture_id`
- `body_family_id`
- `fixture_scope`
- `source_module_ids`
- `primary_mesh_relative_path`
- `fusion_recipe_id`
- `exporter`
- `coordinate_system`

### 6. Package Layout

Recommended first layout:

```text
<fixture_root>/
  canonical_fusion_fixture_manifest.json
  meshes/
    lower_body_core_hi.fbx
  materials/
```

If there are no textures yet, keep `materials/` empty and say so in the manifest.

## Fast Self-Check

Before asking AiUE to treat a package as a real handoff, run:

- [run_check_c2_provider_ready_source_handoff.ps1](C:/AiUE/run_check_c2_provider_ready_source_handoff.ps1)

That check answers:

- does the package itself look like a provider-ready source handoff?
- if not, which package-level fields are still missing?

It intentionally does not require the full repository-integrated `C2` context.

## Full AiUE Gate

After the package-level self-check turns green, run:

- [run_canonical_fusion_fixture_c2.ps1](C:/AiUE/run_canonical_fusion_fixture_c2.ps1)

That is the stricter repository-integrated gate.

## Acceptance For First Qualified C2 Package

AiUE should be able to run:

- [run_canonical_fusion_fixture_c2.ps1](C:/AiUE/run_canonical_fusion_fixture_c2.ps1)

and get:

- `status = pass`

The package-level self-check should also be able to run:

- [run_check_c2_provider_ready_source_handoff.ps1](C:/AiUE/run_check_c2_provider_ready_source_handoff.ps1)

and get:

- `status = pass`
- a provider preview with:
  - `status = ready`
  - `consumer_hints.ready_for_bodypaint = true`

The package does **not** need to be:

- runtime-ready
- rigged
- fully textured
- visually polished

It **does** need to be:

- identified
- replayable
- traceable
- axis-safe

## Linux Automation Direction

The future Linux service should do exactly this:

1. receive raw source zip or canonical input folder
2. run a pinned Houdini recipe
3. export a deterministic mesh path
4. write the manifest
5. emit a zipped `C2` handoff package
6. run AiUE `C2` validation as a post-export check

The first service milestone should not attempt:

- general body generation
- full-body fusion
- rigging
- texture baking

It should only automate:

- deterministic lower-body core fixture export
- deterministic manifest emission
- deterministic validation
