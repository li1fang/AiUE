# ADR-0012: toy-yard Export As The Default Motion Source

## Status

Accepted

## Context

AiUE has now established the motion evidence ladder:

- `M0.5` proved the first shadow-packet seam
- `M1` stabilized the controlled consumer baseline
- `M1.5` proved result-import readiness on the controlled fixture
- `M2` proved fixture diversity across three distinct scenarios
- `M2.5` proved mixed-profile result-import readiness
- `M3` proved the current toy-yard motion export is now a default-source candidate

This changes the strategic question for motion.

The question is no longer:

- can toy-yard motion export be consumed as a trial packet

The new question is:

- how should AiUE promote toy-yard motion export into the default motion source for new runs without collapsing debuggability or reintroducing ownership ambiguity

## Decision

AiUE adopts `toy-yard motion export` as the default motion source for new runs.

This rollout is narrow and evidence-first.

### Rollout Rules

The default motion-source route is fixed as:

1. workspace configs may declare `paths.toy_yard_motion_view_root`
2. when that root is present and valid, AiUE should prefer:
   - `summary/motion_suite_summary.json`
   - `summary/motion_clip_registry.json`
   - `summary/motion_packet_check.json`
   - `summary/communication_signal.json`
   - `clips/<package_id>/manifest.json`
3. when that root is absent, motion workflows should fail loudly rather than silently fall back to ad hoc raw-folder discovery
4. `toy-yard SQLite` remains out of process; it is not a runtime dependency for AiUE motion consumption

### Boundary

This ADR changes default motion-source resolution.

It does **not**:

- make motion quality gates optional
- collapse producer and consumer ownership
- require toy-yard to implement AiUE runtime logic
- remove the historical `M0.5` single-fixture trial evidence

## Consequences

Positive:

- new motion runs can start from portable packets as the normal path
- packet / signal / manifest artifacts become the normal debugging surface
- ownership between toy-yard producer concerns and AiUE consumer concerns stays clearer

Tradeoffs:

- AiUE now depends more on packet consistency in motion summary/registry/manifests
- default-source drift must be caught through explicit switch and quality checkpoints

## Follow-Up

The first implementation slice for this ADR is:

- add a formal motion default-source switch checkpoint
- update example workspace configuration so motion default-source fields are first-class
- keep `M4` as the next quality line so default-source status does not outrun quality evidence
