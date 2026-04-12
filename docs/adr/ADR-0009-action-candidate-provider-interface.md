# ADR-0009: Action Candidate Provider Interface

## Status

Accepted

## Context

AiUE has already proven a controlled demo-ready path for the current two ready bundles.

The next motion-facing question is not "can the host play something" but "what is the contract for an external motion or action candidate source to plug into the platform without bypassing evidence."

That seam needs to be explicit before richer motion-generation work arrives.

## Decision

AiUE adopts an `A1 action candidate provider interface`.

`A1` is a provider seam, not a full motion-generation product.

The first version is fixed as:

- external providers hand AiUE a machine-readable candidate manifest
- the current provider contract only supports `session_animation_preset_ref`
- AiUE consumes the candidate against the existing demo session packages
- AiUE evaluates the resulting `animation_preview` evidence and writes a single latest A1 report
- AiUE also writes three provider-side artifacts:
  - provider context
  - normalized candidate manifest
  - latest provider state

## Interface Rules

The v1 manifest contract is fixed as:

- schema version: `a1_candidate_manifest_v1`
- one provider source per manifest
- one package entry per resolved demo-session package
- at least one candidate per package
- the first candidate is the one executed by `A1`
- supported candidate payload kind:
  - `session_animation_preset_ref`

That means A1 v1 does not yet ingest raw imported motion assets, learned motion clips, or generated pose streams directly.

Instead, it proves the seam using the currently validated session preset surface.

## Prerequisites

`A1` only runs when:

- `DV2` is passing
- `E2C` is passing
- `Dynamic Balance` does not recommend `stabilization`

## Consequences

Positive:

- defines a real integration seam before the future action module arrives
- keeps motion integration evidence-first instead of demo-first
- gives T1 and T2 a stable place to read provider provenance and candidate status

Tradeoffs:

- v1 is intentionally narrow
- motion providers still need to map into an already-known session preset
- raw learned-motion ingestion is deferred to a later phase

## Follow-Up

Future versions may add:

- `animation_asset_path` direct candidate payloads
- richer provider provenance and ranking metadata
- learned-motion outputs such as intermediate pose or curve sequences
- stronger motion-quality gates on top of the same seam
