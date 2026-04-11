# ADR-0006: Dynamic Balance Between Governance And Progress

## Status

Accepted

## Context

AiUE is no longer in the stage where the main question is pure viability.

It now has:

- an active line with stable latest reports
- a platform line with slot, quality, and evidence checkpoints
- a growing governance surface with repeated refactor slices
- `T1/T2` as the current evidence and operator tooling layer

That creates a new coordination problem.

The repo can now drift in two unhealthy directions:

1. continue shipping capability slices while hotspot files and duplicated workflow structure quietly accumulate
2. over-rotate into cleanup and lose visible progress

The project therefore needs a small governance mechanism that can read the current repo state and recommend the next round type without becoming a blocking gate.

## Decision

AiUE adopts `Dynamic Balance Between Governance And Progress` as a first-party soft-signal mechanism.

Version `v1` is fixed as:

- enforcement level: `soft_signal`
- round definition: `checkpoint_round`
- one round = one git commit that touches `docs/checkpoints/*.md`
- signal priorities:
  1. `stabilization`
  2. `governance`
  3. `progress`
  4. `flexible`

`v1` balances exactly three pressures:

- `stability_pressure`
- `governance_pressure`
- `progress_pressure`

`v1` is delivered through:

- an ADR
- a generated latest report
- `T1` evidence-pack integration
- `T2` native workbench integration

It is explicitly **not**:

- a new content capability gate
- a hard blocker on development
- an ownership or staffing system

## Consequences

Positive:

- next-round recommendations are now tied to repo evidence instead of team mood
- governance work and feature work now share one vocabulary
- `T1/T2` can display balance signals next to content and quality signals

Tradeoffs:

- `v1` uses heuristics, not a full project-health model
- checkpoint-round classification is intentionally coarse
- hotspot pressure is file-size and touch-pattern aware, but not semantic

## Follow-up

Possible later expansions:

- recent-run comparison and balance history
- checkpoint override notes
- richer mixed-round detection
- stronger hotspot ownership or domain mapping

Those belong to later `v1.x` work, not the first foundation slice.
