# ADR-0004: Post-Q4 Roadmap And P5 Deferral

## Status

Accepted

## Context

AiUE now has:

- generic slot runtime
- `clothing` vertical slice
- `fx` vertical slice
- multi-slot coexistence
- slot-aware quality gating
- clothing attach hardening
- real FX item kind
- live FX visual proof

The platform is therefore beyond the “prove the slot system exists” stage. The next uncertainty is no longer basic viability; it is whether the measurement layer and interface boundaries are strong enough for richer automated QA and future learned-motion systems.

At the same time, legacy weapon-only fields and APIs still exist as compatibility shims.

## Decision

`P5 Deprecation & Cleanup` is deferred.

Before `P5`, the roadmap will prioritize:

1. `T1 Metrics + Tooling Foundation`
2. `Q5 Dual-Layer Automated Inspection`
3. `A1 Action Candidate Provider Interface`

Only after those areas are stable should the project begin shrinking the legacy weapon-only surface.

## Consequences

Positive:

- avoids cleaning up too early while the platform still lacks stronger measurement and tooling
- keeps the generic slot runtime under real pressure before compatibility removal
- makes later cleanup more confident and less reversible

Tradeoff:

- legacy weapon-only compatibility remains in the codebase for longer
- some duplication and alias fields continue to exist during the transition

## Follow-up

- keep `P4`, `Q4`, and `R3` as current platform proof points
- use `T1` to improve metrics, image analysis, evidence review, and slot debugging
- use `Q5` to extend platform QA from visible correctness to assembly correctness
- use `A1` to define how future motion-generation systems plug into AiUE without being embedded into the shared runtime
