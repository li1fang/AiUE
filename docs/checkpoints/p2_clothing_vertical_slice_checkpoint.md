# P2 Clothing Vertical Slice Checkpoint

## Goal
`P2` proves that AiUE can carry a second wearable axis on top of the generic slot platform introduced in `P1`.

This checkpoint is complete when:

- the demo host can keep the current `weapon` slot active
- a second `clothing` slot can be applied through the generic slot runtime
- the clothing slot can be inspected and visually proven on the same PMX host
- the active line continues to pass after the clothing slice is introduced

## Fixed Fixture
`P2` uses a minimal wearable fixture from `AiUEdemo`:

- clothing slot name: `clothing`
- item kind: `skeletal_mesh`
- attach request: `Head`
- fixture asset: [SKM_Echo_Hair](C:/Users/garro/Documents/Unreal%20Projects/AiUEdemo/Content/Characters/Echo/Meshes/SKM_Echo_Hair.uasset)

The proof gate is:

- [run_clothing_vertical_slice_p2.py](C:/AiUE/workflows/pmx_pipeline/run_clothing_vertical_slice_p2.py)
- [run_clothing_vertical_slice_p2.ps1](C:/AiUE/run_clothing_vertical_slice_p2.ps1)

## Passing Evidence
The latest `P2` report is:

- [latest_clothing_vertical_slice_p2_report.json](C:/AiUE/Saved/verification/latest_clothing_vertical_slice_p2_report.json)

That report proves:

- both ready PMX bundles keep `weapon + clothing` together
- both bundles create a managed `clothing` skeletal mesh component
- both bundles keep non-zero clothing bounds
- both bundles produce passing visual composition checks
- tracked clothing coverage is present in the visual shots

## Runtime And Visual Path
The clothing slice is carried by:

- [PMXCharacterEquipmentComponent.cpp](C:/AiUE/tools/unreal_plugins/AiUEPmxRuntime/Source/AiUEPmxRuntime/Private/PMXCharacterEquipmentComponent.cpp)
- [inspection.py](C:/AiUE/adapters/unreal/host_project/runtime/inspection.py)

`inspect-host-visual` now supports:

- slot binding overrides
- tracked slot coverage in shot payloads

## Residual Risk
`P2` now passes with stronger attach behavior than the original slice:

- one ready bundle resolves `clothing` through a hair-like fallback bone pattern
- the other resolves through a stronger generic PMX fallback bone instead of `owner_origin`

That means the old soft failure mode is gone, but one narrower risk remains:

- some wearable fixtures may still resolve to a generic upper-body PMX anchor instead of a semantically named head or hair socket

That is acceptable for the current platform slice, but it should still be treated as a refinement target before richer clothing semantics are considered finished.

## Active-Line Regression
After `P2`, these latest reports still pass:

- [latest_generic_slot_abstraction_p1_report.json](C:/AiUE/Saved/verification/latest_generic_slot_abstraction_p1_report.json)
- [latest_visual_proof_v1_report.json](C:/AiUE/Saved/verification/latest_visual_proof_v1_report.json)
- [latest_demo_stage_d1_onboarding_report.json](C:/AiUE/Saved/verification/latest_demo_stage_d1_onboarding_report.json)
- [latest_demo_cross_bundle_regression_d12_report.json](C:/AiUE/Saved/verification/latest_demo_cross_bundle_regression_d12_report.json)
- [latest_demo_shot_quality_gate_q1_report.json](C:/AiUE/Saved/verification/latest_demo_shot_quality_gate_q1_report.json)
- [latest_demo_composition_quality_gate_q2_report.json](C:/AiUE/Saved/verification/latest_demo_composition_quality_gate_q2_report.json)
- [latest_demo_semantic_framing_gate_q3_report.json](C:/AiUE/Saved/verification/latest_demo_semantic_framing_gate_q3_report.json)

## Next Step
The next roadmap target remains:

- `P3 FX Vertical Slice`

But a smaller follow-up is also justified:

- tighten clothing attach semantics so more bundles resolve beyond generic fallback bones
