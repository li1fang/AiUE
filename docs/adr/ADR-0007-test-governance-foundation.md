# ADR-0007: Test Governance Foundation

## Status

Accepted

## Context

AiUE has crossed the point where "mainline is viable" is the only important question.

It now has:

- green latest reports across the current active line
- a growing platform line with richer quality evidence
- `T1/T2` as an operator-facing evidence and inspection layer
- a real gap between what is proven in automation and what is only assumed

That gap is now material.

The repo currently proves:

- fixed ready bundles can pass the current verification chain
- native demo control can invoke and read back evidence
- selected quality gates can produce stable artifacts

The repo does **not** yet prove:

- broad character diversity
- broad weapon diversity
- material/texture loading coverage
- manual playable-demo validation

Without a test-governance layer, the project risks presenting "pass" signals that are stronger than the true test coverage.

## Decision

AiUE adopts `Test Governance Foundation` as a first-party governance mechanism alongside `Dynamic Balance`.

Round `TG1` is fixed as:

- priority: `test-first`
- enforcement: `soft signal + light checkpoint threshold`
- output: one generated governance report plus a machine-readable coverage ledger
- purpose: expose coverage blind spots, compute minimum required test lanes for the current change surface, and determine checkpoint readiness

`TG1` is explicitly **not**:

- a new content capability gate
- a full CI policy system
- a replacement for human judgment about roadmap sequencing

## Consequences

Positive:

- the repo can now say what is green and what is still under-covered
- checkpoint packaging gets a minimum explicit lane policy
- `T1/T2` can show testing truth next to feature and quality truth

Tradeoffs:

- first-round coverage is intentionally coarse and axis-based
- path-based lane resolution is heuristic, not semantic
- `TG1` exposes blind spots but does not close them by itself

## Follow-up

Later governance rounds may add:

- richer coverage dimensions
- optional CI export
- stronger lane history / flake tracking
- tighter coupling with `Dynamic Balance`

Those belong to later rounds, not `TG1`.
