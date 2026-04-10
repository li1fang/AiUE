# Generic Slot Platform Roadmap

## Summary

AiUE now has a stable active line for:

- `V1`: kernel visual proof
- `D1`: demo host onboarding
- `D12`: cross-bundle demo regression
- `Q1 -> Q3`: visibility, composition, and semantic framing quality

The next platform direction is to remove the remaining `weapon-only` assumptions from the shared runtime and replace them with a generic slot abstraction that can later host clothing and FX.

## Phases

### P1: Generic Slot Abstraction

Goals:

- Introduce a generic slot binding model in the shared runtime.
- Keep legacy weapon-only fields and APIs as compatibility shims.
- Make both `skeletal_mesh` and `static_mesh` first-class item kinds.
- Fix slot conflict handling as `Override Latest`.
- Prove the generic path with a new `generic_slot_abstraction_p1` gate.

Defaults:

- `weapon` remains the default slot name.
- Conflict key is `SlotName`.
- Same `AttachSocketName` across different slots is allowed and recorded as evidence only.

### P2: Clothing Vertical Slice

Goals:

- Add the first true second equipment axis: `clothing`.
- Validate role + clothing + weapon composition on the demo host.
- Reuse the generic slot runtime rather than adding clothing-only side paths.

### P3: FX Vertical Slice

Goals:

- Add a minimal FX slot on the same generic slot platform.
- Start with attach-to-socket FX only.
- Validate multi-axis composition with character, equipment, and FX.

Current implementation shape:

- first fixture uses a `static_mesh` proxy rather than Niagara
- default fixture: `/Game/Levels/LevelPrototyping/Meshes/SM_Cylinder.SM_Cylinder`
- purpose: prove a third slot axis without introducing a heavier FX runtime dependency too early

### P4: Multi-Slot Composition + QA Expansion

Goals:

- Expand validation from single-axis proofs to multi-slot coexistence.
- Add slot-aware QA for:
  - attach correctness
  - visibility
  - composition
  - runtime conflicts
- Keep reference-image QA out of scope until the slot platform is stable.

Current implementation shape:

- first gate validates `weapon + clothing + fx` on the same host
- `clothing` remains a wearable skeletal mesh fixture
- `fx` remains a `static_mesh` proxy fixture
- first QA expansion only checks coexistence and on-screen co-presence, not semantic correctness

### P5: Deprecation & Cleanup

Goals:

- Retire legacy weapon-only data and runtime shims after `P2` and `P3` are stable.
- Collapse the platform onto the generic slot abstraction as the only active path.

## Current Decisions

- `P1` supports `skeletal_mesh` and `static_mesh`.
- Slot conflicts are `Override Latest`.
- `G2` stays retired.
- `P2` is higher priority than `P3`.
- After `P4` and `Q4`, `P5` is deferred.
- `R1` is complete:
  - clothing no longer falls back to `owner_origin` for the two current ready bundles
  - `Q4` now requires clothing attach resolution to succeed without fallback tolerance
- `R2` is complete:
  - real `niagara_system` item kind now runs through the generic slot runtime
  - the current passing fixture is `/Niagara/DefaultAssets/Templates/Systems/FountainLightweight.FountainLightweight`
  - the current proof uses Niagara system fixed bounds as spatial evidence in the editor-driven inspection path
- The next roadmap priority is:
  - `R3`: live FX visual prominence / semantic FX quality
