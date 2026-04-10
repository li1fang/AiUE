# Generic Slot Platform Roadmap

## Summary

AiUE now has a stable active line for:

- `V1`: kernel visual proof
- `D1`: demo host onboarding
- `D12`: cross-bundle demo regression
- `Q1 -> Q4`: visibility, composition, semantic framing, and multi-slot quality

The platform direction is no longer only about escaping `weapon-only` assumptions. That transition is already complete enough to support a broader roadmap:

- `T1`: metrics and tooling foundation
- `T2`: Windows native workbench
- `Q5`: dual-layer automated inspection
- `A1`: action-candidate provider interface
- `P5`: deferred compatibility cleanup after the stronger QA/tooling layers exist

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

### T1: Metrics + Tooling Foundation

Goals:

- Strengthen the measurement layer before adding heavier QA logic.
- Introduce reusable visual/inspection tooling rather than embedding all analysis inside gates.
- Reduce the cost of understanding evidence across `V1`, `D*`, `P*`, `Q*`, and `R*`.

Planned scope:

- image metrics foundation built on `OpenCV`, `scikit-image`, and `NumPy`
- lightweight Python tests for non-UE evaluation logic
- evidence dashboard for latest reports and key before/after captures
- slot/attach debugger for `slot -> component -> socket/bone -> bounds -> coverage`

Execution rule:

- `T1` is the next direct implementation phase
- it does not replace existing gates
- it exists to make later `Q5` and `A1` work more reliably

Current implementation shape:

- repo-managed tooling env: `C:\AiUE\.venv-tooling`
- Python image metrics with `NumPy`, `OpenCV`, and `scikit-image` available in the tooling environment
- static HTML evidence pack at `Saved/tooling/t1/latest/`
- slot/attach debugger normalized from latest report evidence
- pytest coverage for pure Python tooling logic

### T2: Windows Native Workbench

Goals:

- turn the static T1 evidence pack into a Windows-local diagnostic surface
- keep the tool read-only and evidence-driven rather than mixing in UE execution controls
- expose a machine-readable native-tool state for automated smoke, error-injection, and soak testing

Current implementation shape:

- PySide6 desktop workbench running from `C:\AiUE\.venv-tooling`
- reads `Saved/tooling/t1/latest/manifest.json` or an explicit manifest path
- shows summary cards, report tree, JSON details, preview images, and slot debugger tables
- supports `--dump-state-json` and `--exit-after-load` for automated validation
- validated with `7` open cycles, `3` error injections, and one `5` minute short soak

### Q5: Dual-Layer Automated Inspection

Goals:

- Move platform QA beyond “visible enough” into “assembled correctly.”
- Add deterministic inspection for AI-generated assets without requiring manual review.
- Create the measurement basis for future slot-aware auto-fix.

Layers:

- `Q5A Visible Conflict Inspection`
  - slot/body masking
  - OpenCV-based cross-slot conflict detection
  - specialized QA render passes rather than relying only on final-color screenshots
- `Q5B Spatial Fit Inspection`
  - attach-distance / bounds / overlap / fit checks
  - progressive path toward deeper volumetric embedding inspection
- `Q5C Slot-Aware Auto-Fix`
  - deferred until `Q5A/Q5B` are numerically stable
  - limited, slot-aware offset solving rather than unconstrained transform pushing

Execution rule:

- `Q5` is a post-`T1` QA expansion line
- it should reuse the generic slot runtime and host inspection stack
- it should not be implemented as ad-hoc per-slot scripts

### A1: Action Candidate Provider Interface

Goals:

- Define a clean interface for future motion-generation systems without binding the platform to one model or one vendor.
- Keep learned motion generation external to the shared runtime.
- Let AiUE consume, retarget, preview, and validate motion candidates produced elsewhere.

Planned scope:

- provider-side contract for:
  - prompt
  - current slot state
  - reference images/video
  - candidate motion asset or intermediate representation
- platform-side contract for:
  - candidate import
  - retarget
  - preview
  - gate-based validation

Execution rule:

- `A1` is initially design/interface work only
- no built-in video diffusion or pose-generation stack is planned in the near term
- later action-learning systems should plug into this interface instead of being embedded into `AiUEPmxRuntime`

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
- `R3` is complete:
  - `Saved/verification/latest_live_fx_visual_quality_r3_report.json`
  - current status is `pass`
  - the gate now uses same-session `baseline` vs `with-fx` pair capture on the same spawned host
  - the current passing profile is `SCS_FINAL_COLOR_HDR + warmup`
- `T1` is complete:
  - `tools/bootstrap_t1_tooling.ps1`
  - `tools/run_t1_evidence_pack.ps1`
  - `Saved/tooling/t1/latest/`
  - `docs/checkpoints/t1_metrics_tooling_foundation_checkpoint.md`
- The next roadmap priorities are staged as:
  1. `Q5 Dual-Layer Automated Inspection`
  2. `A1 Action Candidate Provider Interface`
  3. `P5 Deprecation & Cleanup` only after the newer layers have stabilized
