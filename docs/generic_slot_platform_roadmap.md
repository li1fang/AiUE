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
- `E`: demo capability line
- `Q5`: layered automated inspection
- `A1`: action-candidate provider interface
- `P5`: deferred compatibility cleanup after the stronger QA/tooling layers exist

## Phases

### P1: Generic Slot Abstraction

Goals:

- introduce a generic slot binding model in the shared runtime
- keep legacy weapon-only fields and APIs as compatibility shims
- make both `skeletal_mesh` and `static_mesh` first-class item kinds
- fix slot conflict handling as `Override Latest`
- prove the generic path with a new `generic_slot_abstraction_p1` gate

Defaults:

- `weapon` remains the default slot name
- conflict key is `SlotName`
- same `AttachSocketName` across different slots is allowed and recorded as evidence only

### P2: Clothing Vertical Slice

Goals:

- add the first true second equipment axis: `clothing`
- validate role + clothing + weapon composition on the demo host
- reuse the generic slot runtime rather than adding clothing-only side paths

### P3: FX Vertical Slice

Goals:

- add a minimal FX slot on the same generic slot platform
- start with attach-to-socket FX only
- validate multi-axis composition with character, equipment, and FX

Current implementation shape:

- first fixture uses a `static_mesh` proxy rather than Niagara
- default fixture: `/Game/Levels/LevelPrototyping/Meshes/SM_Cylinder.SM_Cylinder`
- purpose: prove a third slot axis without introducing a heavier FX runtime dependency too early

### P4: Multi-Slot Composition + QA Expansion

Goals:

- expand validation from single-axis proofs to multi-slot coexistence
- add slot-aware QA for:
  - attach correctness
  - visibility
  - composition
  - runtime conflicts
- keep reference-image QA out of scope until the slot platform is stable

Current implementation shape:

- first gate validates `weapon + clothing + fx` on the same host
- `clothing` remains a wearable skeletal mesh fixture
- `fx` remains a `static_mesh` proxy fixture
- first QA expansion only checks coexistence and on-screen co-presence, not semantic correctness

### P5: Deprecation & Cleanup

Goals:

- retire legacy weapon-only data and runtime shims after `P2` and `P3` are stable
- collapse the platform onto the generic slot abstraction as the only active path

### T1: Metrics + Tooling Foundation

Goals:

- strengthen the measurement layer before adding heavier QA logic
- introduce reusable visual/inspection tooling rather than embedding all analysis inside gates
- reduce the cost of understanding evidence across `V1`, `D*`, `P*`, `Q*`, and `R*`

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

### E: Demo Capability Line

Goals:

- give `AiUEdemo` a formal capability roadmap instead of treating demo work as scattered gate side-effects
- keep demo outputs evidence-driven before moving into interactivity
- preserve the dual-host boundary:
  - `kernel host` proves composition and minimum correctness
  - `demo host` proves controlled presentation and showcase value

Line shape:

- `E1`: evidence-first showcase demo
- `E2`: playable demo
- `E3`: richer demo orchestration

Execution rule:

- `E1` comes before `E2`
- `E2` starts only after:
  - `E1` first complete pass
  - `2` stable reruns
  - reliable `T2` consumption of `E1` evidence

Current implementation shape:

- [latest_showcase_demo_e1_report.json](C:/AiUE/Saved/verification/latest_showcase_demo_e1_report.json)
- current status is `pass`
- demo evidence is based on:
  - fixed hero shots
  - before/after action frames
  - current ready bundles on `AiUEdemo`
- `E1` is intentionally not a playable UI milestone

### Q5: Dual-Layer Automated Inspection

Goals:

- move platform QA beyond "visible enough" into "assembled correctly"
- add deterministic inspection for AI-generated assets without requiring manual review
- create the measurement basis for future slot-aware auto-fix

Layers:

- `Q5A Visible Conflict Inspection`
  - slot/body masking
  - OpenCV-based cross-slot conflict detection
  - specialized QA render passes rather than relying only on final-color screenshots
- `Q5B Spatial Fit Inspection`
  - attach-distance / bounds / overlap / fit checks
  - progressive path toward deeper volumetric embedding inspection
- `Q5B.x Richer Spatial Evidence`
  - anchor-relative bounds and per-axis clearance evidence
  - fit envelope and evidence-confidence normalization
  - bridge layer between heuristic fit and local volumetric inspection
- `Q5C Slot-Aware Auto-Fix`
  - deferred until `Q5A/Q5B` are numerically stable
  - limited, slot-aware offset solving rather than unconstrained transform pushing

Execution rule:

- `Q5` is a post-`T1` QA expansion line
- it should reuse the generic slot runtime and host inspection stack
- it should not be implemented as ad-hoc per-slot scripts

### A1: Action Candidate Provider Interface

Goals:

- define a clean interface for future motion-generation systems without binding the platform to one model or one vendor
- keep learned motion generation external to the shared runtime
- let AiUE consume, retarget, preview, and validate motion candidates produced elsewhere

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

- `P1` supports `skeletal_mesh` and `static_mesh`
- slot conflicts are `Override Latest`
- `G2` stays retired
- `P2` is higher priority than `P3`
- after `P4` and `Q4`, `P5` is deferred
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
- `Q5A` is complete:
  - [latest_visible_conflict_inspection_q5a_report.json](C:/AiUE/Saved/verification/latest_visible_conflict_inspection_q5a_report.json)
  - current status is `pass`
- `Q5B` is complete:
  - [latest_volumetric_fit_inspection_q5b_report.json](C:/AiUE/Saved/verification/latest_volumetric_fit_inspection_q5b_report.json)
  - current status is `pass`
- `Q5B.x` is complete:
  - [latest_volumetric_fit_spatial_evidence_q5bx_report.json](C:/AiUE/Saved/verification/latest_volumetric_fit_spatial_evidence_q5bx_report.json)
  - current status is `pass`
- `Q5C-lite` is complete:
  - [latest_volumetric_inspection_q5c_lite_report.json](C:/AiUE/Saved/verification/latest_volumetric_inspection_q5c_lite_report.json)
  - current status is `pass`
- `E1` is complete:
  - [latest_showcase_demo_e1_report.json](C:/AiUE/Saved/verification/latest_showcase_demo_e1_report.json)
  - current status is `pass`
- `T1` is complete:
  - `tools/bootstrap_t1_tooling.ps1`
  - `tools/run_t1_evidence_pack.ps1`
  - `Saved/tooling/t1/latest/`
  - `docs/checkpoints/t1_metrics_tooling_foundation_checkpoint.md`

## Current Priority Order

The near-term priority order is now:

1. keep `E1` stable enough to unlock `E2`
2. deepen `Q5` evidence from `Q5B.x` and `Q5C-lite`
3. define `A1` as a clean external interface
4. defer `P5` cleanup until the newer lines have truly stabilized
