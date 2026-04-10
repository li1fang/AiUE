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

However, two intentionally soft assumptions remain:

1. one ready bundle may still use `owner_origin` for `clothing`
2. `fx` is currently represented by a `static_mesh` proxy rather than a true effect runtime

At the same time, legacy weapon-only fields and APIs still exist as compatibility shims.

## Decision

`P5 Deprecation & Cleanup` is deferred.

Before `P5`, the roadmap will prioritize:

1. `R1 Clothing Attach Hardening`
2. `R2 Real FX Item Kind`

Only after those two areas are stable should the project begin shrinking the legacy weapon-only surface.

## Consequences

Positive:

- avoids cleaning up too early while key runtime assumptions are still soft
- keeps the generic slot runtime under real pressure before compatibility removal
- makes later cleanup more confident and less reversible

Tradeoff:

- legacy weapon-only compatibility remains in the codebase for longer
- some duplication and alias fields continue to exist during the transition

## Follow-up

- keep `P4` and `Q4` as the current platform proof points
- use `R1` to reduce clothing fallback reliance
- use `R2` to graduate FX from proxy slot to real runtime kind
