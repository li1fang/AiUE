# C2 Converted Model Provider v0.1 Checkpoint

## Goal

This node turns the internal `C2` Houdini handoff report into a stable consumer seam.

It answers a narrower question than `C2` itself:

`Can AiUE hand a downstream tool one small JSON file that says which converted body mesh is ready, where it lives, and what evidence travels with it?`

## Why It Exists

`C2` proves that Houdini can hand AiUE a replayable fusion artifact.

But a downstream tool such as `BodyPaint` should not need to:

- understand the full `C2` report envelope
- infer which mesh is the recommended converted model
- guess which manifest or texture directory belongs to that mesh

The converted-model provider keeps that seam thin and explicit.

## Delivery Shape

AiUE now emits:

- `converted_model_provider.json`
- `converted_model_provider_latest.json`
- `Saved/body_platform/c2/latest/converted_model_provider_v0_1.json`

The payload follows:

- `version = aiue-converted-model-provider-0.1`
- a narrow `status`
- one `primary_asset`
- optional `companions`
- lineage and conversion provenance
- lightweight `consumer_hints`
- a small `body_platform` block with stable handoff identity:
  - `source_gate_id`
  - `body_family_id`
  - `fixture_id`
  - `fixture_scope`
  - `fusion_recipe_id`
  - `rig_profile_id`
  - `material_profile_id`

## Current Source

`v0.1` is derived from:

- `latest_canonical_fusion_fixture_c2_report.json`

That means the seam stays aligned with the current body-platform truth source, instead of inventing a parallel registry.

## Status Rules

The current provider status is intentionally narrow:

- `ready`
- `missing_primary_asset`
- `missing_manifest`
- `conversion_failed`
- `not_found`

`ready` means the converted model is resolvable enough for a consumer such as `BodyPaint` to start from it.

It does not mean:

- rig complete
- runtime-ready avatar
- final material quality approved

## BodyPaint Boundary

The provider intentionally exposes only upstream converted-model facts:

- what the converted model is
- where the primary asset is
- which companion artifacts travel with it
- how it was produced
- which body-platform fixture it belongs to

It intentionally does not expose BodyPaint-owned concepts such as:

- `resolved_axes`
- `regions`
- `paint_strategy`
- `manual_overrides`

## Resolver Entry

AiUE also provides a thin resolver wrapper:

- [run_resolve_converted_model_provider_v0.ps1](C:\AiUE\run_resolve_converted_model_provider_v0.ps1)

That wrapper exists so downstream automation can ask for the latest provider payload without reading the full `C2` report directly.

## Next Step

With this seam in place, the next step is not another contract rewrite.

The next step is to let the first real downstream consumer use it and report back where the seam is still too thin or too implicit.
