# ADR-0008: Post-PV1 Automation-First Roadmap

## Status

Accepted

## Context

AiUE has now crossed another important threshold.

The repo currently has:

- green latest reports across the active line
- green latest reports across the current platform line
- `M1` material and texture proof promoted into the automated verification path
- `E2B` credible showcase evidence proving that the current ready bundles can be presented with character, weapon, clothing, FX, and verified motion evidence
- `PV1` manual playable-demo signoff wired into governance and evidence surfaces, but still honestly pending a real human operator pass

That means the main uncertainty has shifted again.

The question is no longer:

- whether AiUE can prove a controlled ready-bundle path exists
- whether demo evidence can be generated at all
- whether governance can expose blind spots

The next question is how to extend confidence without confusing demo polish with validation authority.

The project now needs an explicit rule for what comes next.

## Decision

AiUE adopts a `post-PV1 automation-first roadmap`.

The roadmap is fixed as:

1. `DV2`: automated diversity expansion
2. `E2C`: credible showcase polish
3. `A1`: action candidate provider / motion-integration seam

`PV1` remains a governance signoff track that can run in parallel, but it does **not** become the authority that decides whether automation is trustworthy.

### Priority Rules

AiUE fixes the following development rules:

- playable demo remains presentation-first, not validation-first
- automation quality remains the primary authority for confidence
- manual playable-demo signoff remains governance evidence, not automation evidence
- demo polish follows proven evidence breadth instead of replacing it
- future motion integration should plug into an already measured and evidence-rich platform

### Entry Rules

`DV2` may begin immediately.

It is **not** blocked by `PV1` being pending, because `PV1` is a manual signoff concern rather than an automation readiness concern.

`E2C` begins only after:

- `DV2` has a first full pass
- `DV2` has at least `1` stable rerun
- `T1/T2` can consume the resulting diversity evidence without regressions

`A1` begins only after:

- `DV2` has established broader automated coverage
- `E2C` has produced a more credible presentation bundle
- `Dynamic Balance` does not recommend `stabilization`

`PV1` manual signoff remains recommended before:

- external packaging
- milestone-style demo handoff
- stronger project-facing presentation claims

But it does not block continued automation-first engineering.

## Consequences

Positive:

- keeps validation authority anchored in automation rather than in demo feel
- lets the team continue forward without pretending that missing human signoff is an automation failure
- creates a clean order: broaden truth first, then polish what is shown, then integrate richer motion systems
- gives future action-generation work a better host, evidence, and QA surface to plug into

Tradeoffs:

- the playable demo may remain less "finished" for a while than the underlying platform actually is
- broader diversity pressure now becomes the next hard engineering problem
- `PV1` remains visibly unresolved until a real human signoff happens

## Follow-Up

The follow-up route is fixed as:

- `DV2`: promote diversity axes beyond the current narrow ready-bundle path
- `E2C`: turn current credible showcase evidence into a more convincing polished demo bundle
- `A1`: define the seam for future learned-motion or external action-candidate systems
- keep `PV1` honest and governance-only until a human operator actually signs it off

The repo should not treat "playable" as proof.
It should treat "playable" as the thing shown **after** proof becomes broad enough to deserve showing.
