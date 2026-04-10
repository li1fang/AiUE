# R2 Real FX Item Kind Checkpoint

## Summary

`R2` upgrades the generic slot platform from a `static_mesh` FX proxy to a real `niagara_system` item kind.

This work proves that the shared runtime can now:

- carry a Niagara-backed slot binding through the same generic slot data path as `weapon` and `clothing`
- create and attach a `NiagaraComponent` on both ready bundles
- preserve the resolved FX attach state in runtime and visual inspection
- project Niagara system spatial evidence into shot coverage using the system's own fixed bounds

`R2` is therefore a real platform milestone, not just a demo-side workaround.

## Core Changes

Key runtime changes landed in:

- `tools/unreal_plugins/AiUEPmxRuntime/AiUEPmxRuntime.uplugin`
- `tools/unreal_plugins/AiUEPmxRuntime/Source/AiUEPmxRuntime/AiUEPmxRuntime.Build.cs`
- `tools/unreal_plugins/AiUEPmxRuntime/Source/AiUEPmxRuntime/Public/PMXEquipmentReflection.h`
- `tools/unreal_plugins/AiUEPmxRuntime/Source/AiUEPmxRuntime/Public/PMXCharacterEquipmentComponent.h`
- `tools/unreal_plugins/AiUEPmxRuntime/Source/AiUEPmxRuntime/Private/PMXCharacterEquipmentComponent.cpp`

Key inspection/runtime changes landed in:

- `adapters/unreal/host_project/runtime/common.py`
- `adapters/unreal/host_project/runtime/composition.py`
- `adapters/unreal/host_project/runtime/inspection.py`

Key gate entrypoints:

- `run_real_fx_item_kind_r2.ps1`
- `workflows/pmx_pipeline/run_real_fx_item_kind_r2.py`

## What Changed

### Generic slot runtime

The shared runtime now recognizes a third generic item kind:

- `niagara_system`

Slot bindings can now carry:

- `niagara_system_asset`

The shared equipment component now:

- creates a `NiagaraComponent` for `niagara_system` bindings
- keeps the resolved attach state under the same slot-aware reporting model
- preserves backward compatibility for the existing `weapon` and `clothing` paths

### Niagara dependency wiring

The shared plugin now declares Niagara as an explicit dependency, so both hosts compile with the same runtime surface:

- `UEIntroProject`
- `AiUEdemo`

### Spatial evidence fallback

The important inspection hardening landed in:

- `adapters/unreal/host_project/runtime/common.py`

`NiagaraComponent.bounds` remained zero in the current editor-driven proof path, even when the asset and attach state were valid.

`R2` therefore adds a Niagara-aware fallback that reads:

- `fixed_bounds`
- `initial_streaming_bounds`

from the Niagara system asset itself.

This is why `R2` now resolves non-zero FX bounds with:

- `source = niagara_fixed_bounds_property`

## Validation

Latest passing report:

- `Saved/verification/latest_real_fx_item_kind_r2_report.json`

Current passing fixture:

- Niagara system: `/Niagara/DefaultAssets/Templates/Systems/FountainLightweight.FountainLightweight`

Current outcome:

- ready packages resolved: `2`
- runtime checks passed: `2/2`
- visual checks passed: `2/2`
- passing FX visual shots: `6`

Resolved attach results:

- `mingchao_sample_c0aeb7ff_character_35215ba5`
  - attach mode: `fallback_bone_score`
  - target: `Bone_dummy_D_R_012`
- `mingchao_xjqy8yn4h6_b6e33424_character_f91ab5d6`
  - attach mode: `fallback_bone_score`
  - target: `Bone_dummy_D_R_040`

Regression checks also continue to pass:

- `P3`: `Saved/verification/latest_fx_vertical_slice_p3_report.json`
- `P4`: `Saved/verification/latest_multi_slot_composition_p4_report.json`
- `Q4`: `Saved/verification/latest_multi_slot_quality_gate_q4_report.json`

## Important Limitation

`R2` does **not** yet prove strong live-particle readability in the final screenshot.

What it proves today is narrower and still valuable:

- real Niagara item kind is wired into the generic slot runtime
- the managed FX component is created and attached correctly
- the bound Niagara system asset is preserved end-to-end
- the system carries valid spatial evidence through fixed bounds

What remains for a later phase is:

- stronger proof that the captured pixels show a visually prominent live FX effect, not just a valid Niagara runtime envelope

## Decision

`R2` is complete enough to advance the roadmap.

Recommended next roadmap priority:

- `R3`: live FX visual prominence / semantic FX quality
