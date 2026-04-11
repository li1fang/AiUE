# ADR-0005: Demo Capability Line

## Status

Accepted

## Context

AiUE already proved that the shared runtime and dual-host structure are viable.

At this stage, the question is no longer whether the project can render a character at all.
The question is how demo-facing capability should evolve without collapsing back into an unstructured mix of:

- validation gates
- ad-hoc screenshots
- presentation experiments
- host-specific behavior

The project also needs to avoid promoting a playable demo too early, before the evidence and tooling layers are strong enough.

## Decision

AiUE adopts an explicit demo capability line:

1. `E1`: evidence-first showcase demo
2. `E2`: playable demo
3. `E3`: richer demo orchestration

The line is gated by capability thresholds rather than dates.

`E1` comes first.
`E2` does not begin until:

- `E1` has a first full pass
- `E1` has `2` stable reruns
- `T2` can read the latest `E1` evidence reliably

This entry condition is operationalized through the internal `showcase_demo_e1_stability` gate,
which reruns `E1` twice, refreshes `T1`, and verifies `T2 --latest` consumption.

## Consequences

Positive:

- keeps demo work tied to proof and evidence rather than drifting into isolated presentation logic
- protects the platform from starting interactive work before the diagnostics are ready
- gives `AiUEdemo` a clear long-term role without overloading `UEIntroProject`

Tradeoff:

- some highly visible "playable" value is deferred
- the first demo milestone is intentionally report-driven rather than user-interactive

## Follow-Up

- keep `E1` as the current demo milestone
- treat playable demo work as `E2`, not as silent scope creep inside `E1`
- let `T1/T2` remain the evidence surfaces for both platform and demo lines
- use `showcase_demo_e1_stability` as the concrete threshold check before opening `E2`
