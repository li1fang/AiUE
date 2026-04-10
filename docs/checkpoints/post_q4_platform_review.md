# Post-Q4 Platform Review

## Summary

After `P1 -> P4` and `Q1 -> Q4`, AiUE is no longer a weapon-only demo line.

It now has:

- a dual-host structure
- a shared Unreal runtime plugin
- generic slot data and runtime application
- validated `weapon + clothing + fx` coexistence
- slot-aware quality gates on top of coexistence

This means the project has crossed an important line:

- it is no longer asking "can this workflow be made to work at all?"
- it is now asking "which remaining assumptions should be hardened, and in what order, before cleanup removes compatibility shims?"

## Current Active Evidence

The current active evidence chain is:

- `V1` kernel visual proof
- `D1` demo host onboarding
- `D12` cross-bundle demo regression
- `Q1 -> Q3` subject/composition/semantic framing
- `P1` generic slot abstraction
- `P2` clothing vertical slice
- `P3` FX vertical slice
- `P4` multi-slot composition
- `Q4` multi-slot quality

Current latest reports:

- `V1`: `Saved/verification/latest_visual_proof_v1_report.json`
- `D1`: `Saved/verification/latest_demo_stage_d1_onboarding_report.json`
- `D12`: `Saved/verification/latest_demo_cross_bundle_regression_d12_report.json`
- `P1`: `Saved/verification/latest_generic_slot_abstraction_p1_report.json`
- `P2`: `Saved/verification/latest_clothing_vertical_slice_p2_report.json`
- `P3`: `Saved/verification/latest_fx_vertical_slice_p3_report.json`
- `P4`: `Saved/verification/latest_multi_slot_composition_p4_report.json`
- `Q4`: `Saved/verification/latest_multi_slot_quality_gate_q4_report.json`

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

### 5. Quality gates

Status: strong but intentionally narrow

Reason:

- `Q1 -> Q4` are now progressively stricter
- `Q4` is the first gate that explicitly reasons about `weapon + clothing + fx` together

Current judgment:

- the quality line is now meaningful
- but it is still image-evidence QA, not full content QA

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

### 1. Clothing owner-origin fallback still exists

This is the most visible unresolved runtime quality issue.

Current evidence:

- `Q4` passes
- but one ready package still uses `owner_origin` for `clothing`
- that fallback is tolerated only because the component is valid and remains visible

Why it matters:

- this is acceptable as a transitional rule
- it is not a good long-term platform invariant

### 2. FX is still a static-mesh proxy

This is intentional, not an accident.

Current evidence:

- `P3` and `P4` prove a third slot axis
- but they do not yet prove a true time-based effect system

Why it matters:

- the platform can carry a third slot
- but not yet a real production FX runtime

### 3. Legacy weapon API is still present

This is expected technical debt.

Why it matters:

- the plugin is now generic in spirit
- but not yet fully generic in public surface

## Decision

Do **not** start `P5 Deprecation & Cleanup` yet.

Reason:

- the generic slot path is proven
- but two quality-adjacent platform assumptions are still intentionally soft:
  - clothing attach fallback
  - FX as static-mesh proxy

If `P5` starts too early, cleanup will remove compatibility pressure before these soft assumptions are either hardened or explicitly replaced.

## Recommended Next Phases

### R1: Clothing Attach Hardening

Goal:

- reduce or eliminate `owner_origin` fallback for `clothing`
- improve slot-specific attach heuristics for wearable content

Success condition:

- the current two ready bundles both resolve `clothing` to a meaningful bone/socket target
- `Q4` keeps passing without relying on `allow_clothing_owner_origin_fallback`

### R2: Real FX Item Kind

Goal:

- add a real effect-carrying item kind instead of only `static_mesh` proxy FX
- likely candidate: a dedicated effect asset path and runtime component type

Success condition:

- `fx` no longer means only `static_mesh`
- the platform can host a real FX slot without breaking `P4/Q4`

### P5: Deprecation & Cleanup

Goal:

- only after `R1` and `R2` are stable
- begin shrinking weapon-only shims and legacy compatibility fields

Success condition:

- generic slot runtime is the only true active path
- legacy weapon-only APIs are either removed or clearly marked transitional

## Final Assessment

The project is now in a much better position than during the early host/capture phase.

The biggest shift is this:

- before `P1`, the system mostly proved that a narrow character+weapon line could be made to work
- after `P4/Q4`, the system proves that AiUE can behave like a reusable content platform with multiple equipment axes and layered quality checks

That does not mean the platform is finished.

It means the next work should be selective and architectural:

- harden the two remaining soft assumptions
- then clean up compatibility
- then expand to richer content QA
