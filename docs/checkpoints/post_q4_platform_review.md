# Post-Q4 Platform Review

## Summary

After `P1 -> P4`, `Q1 -> Q4`, and the follow-up hardening line `R1 -> R3`, AiUE is no longer a weapon-only demo line.

It now has:

- a dual-host structure
- a shared Unreal runtime plugin
- generic slot data and runtime application
- validated `weapon + clothing + fx` coexistence
- slot-aware quality gates on top of coexistence
- live Niagara FX screenshot evidence

This means the project has crossed an important line:

- it is no longer asking "can this workflow be made to work at all?"
- it is now asking "which remaining assumptions should be hardened, and in what order, before cleanup removes compatibility shims?"

## Current Active Evidence

The current active evidence chain is:

- `V1` kernel visual proof
- `D1` demo host onboarding
- `D12` cross-bundle demo regression
- `Q1 -> Q4` subject/composition/semantic framing/multi-slot quality
- `P1` generic slot abstraction
- `P2` clothing vertical slice
- `P3` FX vertical slice
- `P4` multi-slot composition
- `Q4` multi-slot quality
- `R1` clothing attach hardening
- `R2` real FX item kind
- `R3` live FX visual quality

Current latest reports:

- `V1`: `Saved/verification/latest_visual_proof_v1_report.json`
- `D1`: `Saved/verification/latest_demo_stage_d1_onboarding_report.json`
- `D12`: `Saved/verification/latest_demo_cross_bundle_regression_d12_report.json`
- `P1`: `Saved/verification/latest_generic_slot_abstraction_p1_report.json`
- `P2`: `Saved/verification/latest_clothing_vertical_slice_p2_report.json`
- `P3`: `Saved/verification/latest_fx_vertical_slice_p3_report.json`
- `P4`: `Saved/verification/latest_multi_slot_composition_p4_report.json`
- `Q4`: `Saved/verification/latest_multi_slot_quality_gate_q4_report.json`
- `R1`: validated through the latest `P2/P4/Q4` reports
- `R2`: `Saved/verification/latest_real_fx_item_kind_r2_report.json`
- `R3`: `Saved/verification/latest_live_fx_visual_quality_r3_report.json`

## Module Assessment

### 1. Dual-host architecture

Status: strong

Reason:

- `UEIntroProject` is now clearly the kernel host.
- `AiUEdemo` is now clearly the demo host.
- This split reduced the original confusion between automation control and presentation control.

Current judgment:

- keep this architecture
- do not collapse back to one host

### 2. Shared Unreal runtime plugin

Status: strong

Reason:

- the runtime is no longer project-local glue
- core slot logic lives in `AiUEPmxRuntime`
- `P1 -> P4` all depend on the same runtime path

Current judgment:

- this plugin is now the real platform center
- future feature work should continue to land here first

### 3. Generic slot abstraction

Status: strong

Reason:

- slot data now supports `skeletal_mesh` and `static_mesh`
- slot conflict policy is explicit: `Override Latest`
- multi-slot coexistence is proven, not just theorized

Current judgment:

- the generic slot abstraction is good enough to serve as the base for later `clothing`, `fx`, and broader composition work

### 4. Visual and demo regression line

Status: medium-strong

Reason:

- the visual proof and demo gates are stable
- multi-animation and cross-bundle evidence are already in place
- the system can now produce repeated image evidence with stronger quality checks

Current judgment:

- good enough to rely on for future vertical slices
- should continue to be treated as a verification layer, not as the primary location for platform logic

### 5. Quality gates and FX visual proof

Status: strong and expanding in the right direction

Reason:

- `Q1 -> Q4` are now progressively stricter
- `Q4` is the first gate that explicitly reasons about `weapon + clothing + fx` together
- `R3` closes the earlier gap between “FX component exists” and “FX pixels really enter the screenshot”

Current judgment:

- the quality line is now meaningful
- but it is still mostly screenshot/evidence QA, not full automated content QA

### 6. Legacy compatibility layer

Status: acceptable, but now clearly technical debt

Reason:

- weapon-specific fields and APIs were preserved intentionally through `P1`
- that was the correct choice during the transition
- but after `P4/Q4`, the generic path is no longer hypothetical

Current judgment:

- legacy shims should be kept for now
- but only as temporary compatibility, not as permanent architecture

## Remaining Risks

### 1. Runtime modules are large enough to warrant another structure pass

This is now the clearest maintainability risk.

Current evidence:

- [retarget.py](C:/AiUE/adapters/unreal/host_project/runtime/retarget.py) is large enough to behave like a subsystem
- [common.py](C:/AiUE/adapters/unreal/host_project/runtime/common.py) is carrying too many cross-domain helpers
- workflow runners are numerous enough that tooling and discoverability now matter

Why it matters:

- the platform is succeeding functionally
- but its internal cost of extension is climbing

### 2. Legacy weapon API is still present

This is expected technical debt.

Why it matters:

- the plugin is now generic in spirit
- but not yet fully generic in public surface

## Decision

Do **not** start `P5 Deprecation & Cleanup` yet.

Reason:

- the generic slot path is proven
- `R1 -> R3` have removed the most obvious runtime softness
- but the platform still needs better metrics, better tools, and a clearer bridge toward richer QA and future motion-generation systems

If `P5` starts too early, cleanup will consume bandwidth that is better spent on stronger measurement and interfaces.

## Recommended Next Phases

### T1: Metrics + Tooling Foundation

Goal:

- strengthen image and inspection metrics before heavier QA phases
- build the tooling needed to inspect evidence and slot state quickly

Success condition:

- the platform has reusable image-analysis utilities
- latest reports and key artifacts are easier to inspect
- slot/attach debugging no longer depends on manually reading raw JSON

Current status:

- complete
- checkpoint: `docs/checkpoints/t1_metrics_tooling_foundation_checkpoint.md`
- evidence pack: `Saved/tooling/t1/latest/`

### T2: Windows Native Workbench

Goal:

- add a Windows-local evidence and diagnostics surface on top of `T1`
- make report/image/slot evidence easier to inspect without relying on browser access

Success condition:

- latest `T1` evidence packs can be opened in a native desktop workbench
- the workbench exposes machine-readable state for automated validation
- the tool survives repeated launch, error-injection, and short soak testing

Current status:

- complete
- checkpoint: `docs/checkpoints/t2_windows_native_workbench_checkpoint.md`
- entry points:
  - `tools/run_t2_workbench.ps1`
  - `tools/run_t2_workbench_tests.ps1`

### Q5: Dual-Layer Automated Inspection

Goal:

- add deterministic assembly QA on top of the current visual proof line
- combine visible conflict checks with spatial/fit checks

Success condition:

- the platform can automatically flag visible cross-slot conflicts
- the platform can quantify attach-fit quality strongly enough to support future slot-aware auto-fix

### A1: Action Candidate Provider Interface

Goal:

- define the boundary for future motion-generation systems without embedding them into the runtime

Success condition:

- AiUE has a clean ingestion/preview/validation interface for externally produced motion candidates
- future learned action systems can plug into the platform without rewriting the host runtime

### P5: Deprecation & Cleanup

Goal:

- only after `T1`, `Q5`, and the first `A1` interface pass are stable
- begin shrinking weapon-only shims and legacy compatibility fields

Success condition:

- generic slot runtime is the only true active path
- legacy weapon-only APIs are either removed or clearly marked transitional

## Final Assessment

The project is now in a much better position than during the early host/capture phase.

The biggest shift is this:

- before `P1`, the system mostly proved that a narrow character+weapon line could be made to work
- after `P4/Q4`, the system proves that AiUE can behave like a reusable content platform with multiple equipment axes and layered quality checks
- after `R3`, the system also proves that real FX can be measured at the final screenshot layer

That does not mean the platform is finished.

It means the next work should be selective and architectural:

- build stronger metrics and debugging tools
- extend the new native workbench as the local evidence surface when useful
- add dual-layer automated inspection
- define the future action-candidate interface
- then clean up compatibility
