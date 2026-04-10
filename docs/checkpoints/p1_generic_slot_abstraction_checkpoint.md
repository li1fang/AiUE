# P1 Generic Slot Abstraction Checkpoint

## Goal
`P1` upgrades AiUE from a weapon-centric runtime into a generic slot platform while preserving the active line:

- `V1`
- `D1`
- `D12`
- `Q1`
- `Q2`
- `Q3`

This checkpoint is complete when:

- the shared runtime accepts generic slot bindings
- both `skeletal_mesh` and `static_mesh` are runtime-ready item kinds
- legacy weapon-only data and APIs still work through compatibility shims
- same-slot conflicts resolve as `Override Latest`
- the active line still passes after the slot abstraction is introduced

## Platform Changes
The shared Unreal runtime now carries slot-aware data and runtime behavior in:

- [PMXEquipmentReflection.h](C:/AiUE/tools/unreal_plugins/AiUEPmxRuntime/Source/AiUEPmxRuntime/Public/PMXEquipmentReflection.h)
- [PMXCharacterEquipmentComponent.h](C:/AiUE/tools/unreal_plugins/AiUEPmxRuntime/Source/AiUEPmxRuntime/Public/PMXCharacterEquipmentComponent.h)
- [PMXCharacterEquipmentComponent.cpp](C:/AiUE/tools/unreal_plugins/AiUEPmxRuntime/Source/AiUEPmxRuntime/Private/PMXCharacterEquipmentComponent.cpp)
- [PMXEquipmentBlueprintLibrary.h](C:/AiUE/tools/unreal_plugins/AiUEPmxRuntime/Source/AiUEPmxRuntime/Public/PMXEquipmentBlueprintLibrary.h)
- [PMXEquipmentBlueprintLibrary.cpp](C:/AiUE/tools/unreal_plugins/AiUEPmxRuntime/Source/AiUEPmxRuntime/Private/PMXEquipmentBlueprintLibrary.cpp)

The runtime now supports:

- generic `SlotBindings`
- `skeletal_mesh` items
- `static_mesh` items
- managed components by slot
- slot attach-state evidence
- slot conflict evidence
- legacy `weapon` compatibility shims

## Host And Python Path
The host-side slot-aware path now flows through:

- [common.py](C:/AiUE/adapters/unreal/host_project/runtime/common.py)
- [composition.py](C:/AiUE/adapters/unreal/host_project/runtime/composition.py)
- [inspection.py](C:/AiUE/adapters/unreal/host_project/runtime/inspection.py)
- [preview.py](C:/AiUE/adapters/unreal/host_project/runtime/preview.py)
- [aiue_host_bridge.py](C:/AiUE/adapters/unreal/host_project/aiue_host_bridge.py)
- [command_catalog.py](C:/AiUE/adapters/unreal/python/aiue_unreal/command_catalog.py)
- [host_bridge.py](C:/AiUE/adapters/unreal/python/aiue_unreal/host_bridge.py)
- [auto_ue_cli.ps1](C:/AiUE/adapters/powershell/auto_ue_cli.ps1)

The new internal proof gate is:

- [run_generic_slot_abstraction_p1.py](C:/AiUE/workflows/pmx_pipeline/run_generic_slot_abstraction_p1.py)
- [run_generic_slot_abstraction_p1.ps1](C:/AiUE/run_generic_slot_abstraction_p1.ps1)

## Fixed Rules
`P1` locks these rules:

- `weapon` remains the default slot name
- `SlotName` is the conflict key
- same-slot writes resolve as `Override Latest`
- superseded bindings are retained as evidence
- different slots may share the same attach socket without failing the gate

## Passing Evidence
`P1` is now passing. The latest proof is:

- [latest_generic_slot_abstraction_p1_report.json](C:/AiUE/Saved/verification/latest_generic_slot_abstraction_p1_report.json)

That report proves:

- `2` ready weapon bundles still apply through the generic slot path
- the `weapon` slot remains compatible with the current active line
- a `static_mesh` smoke slot can be attached and inspected on the demo host
- latest-override conflict evidence is emitted

## Active-Line Regression
After `P1`, the active-line latest reports still pass:

- [latest_visual_proof_v1_report.json](C:/AiUE/Saved/verification/latest_visual_proof_v1_report.json)
- [latest_demo_stage_d1_onboarding_report.json](C:/AiUE/Saved/verification/latest_demo_stage_d1_onboarding_report.json)
- [latest_demo_cross_bundle_regression_d12_report.json](C:/AiUE/Saved/verification/latest_demo_cross_bundle_regression_d12_report.json)
- [latest_demo_shot_quality_gate_q1_report.json](C:/AiUE/Saved/verification/latest_demo_shot_quality_gate_q1_report.json)
- [latest_demo_composition_quality_gate_q2_report.json](C:/AiUE/Saved/verification/latest_demo_composition_quality_gate_q2_report.json)
- [latest_demo_semantic_framing_gate_q3_report.json](C:/AiUE/Saved/verification/latest_demo_semantic_framing_gate_q3_report.json)

## Next Step
The next platform step is defined by the roadmap at:

- [generic_slot_platform_roadmap.md](C:/AiUE/docs/generic_slot_platform_roadmap.md)

The next implementation target is:

- `P2 Clothing Vertical Slice`
