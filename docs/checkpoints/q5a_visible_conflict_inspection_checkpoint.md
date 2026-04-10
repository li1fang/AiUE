# Q5A Visible Conflict Inspection Checkpoint

## Summary

`Q5A` is the first visible-conflict quality gate on top of the generic slot platform.

Its scope is intentionally narrow:

- host: `demo`
- slots under inspection: `body` vs `clothing`
- fixture: `SKM_Echo_Hair`
- shots: `front` and `side`

The goal is not full semantic clothing QA. The goal is to prove that AiUE can run a deterministic inspection loop:

- apply a ready bundle on the demo host
- emit dedicated QA capture passes
- analyze visible conflict with Python/OpenCV
- write a gate-style report
- surface the result through `T1` and `T2`

## Passing Evidence

The current passing report is:

- [latest_visible_conflict_inspection_q5a_report.json](C:/AiUE/Saved/verification/latest_visible_conflict_inspection_q5a_report.json)

Current passing outcome:

- `status = pass`
- `packages = 2`
- `passing_packages = 2`
- `shot_sets = 4`
- `passing_shot_sets = 4`
- `raw_pass_images = 12`
- `debug_overlays = 4`
- `color_threshold_shot_sets = 4`
- `silhouette_fallback_shot_sets = 0`

The first full-pass discussion signal is also present:

- `discussion_signal.reason = first_complete_q5a_pass`

## What Landed

The main pieces are:

- shared plugin QA content:
  - [AiUEPmxRuntime.uplugin](C:/AiUE/tools/unreal_plugins/AiUEPmxRuntime/AiUEPmxRuntime.uplugin)
  - [create_q5a_plugin_assets.py](C:/AiUE/tools/unreal/create_q5a_plugin_assets.py)
  - [ensure_q5a_plugin_assets.ps1](C:/AiUE/tools/ensure_q5a_plugin_assets.ps1)
- host command and runtime path:
  - [inspect_visible_conflict.py](C:/AiUE/adapters/unreal/python/aiue_unreal/commands/inspect_visible_conflict.py)
  - [inspection.py](C:/AiUE/adapters/unreal/host_project/runtime/inspection.py)
  - [capture.py](C:/AiUE/adapters/unreal/host_project/runtime/capture.py)
  - [common.py](C:/AiUE/adapters/unreal/host_project/runtime/common.py)
- Python analysis and gate:
  - [q5a_visible_conflict.py](C:/AiUE/tools/t1/python/aiue_t1/q5a_visible_conflict.py)
  - [run_visible_conflict_inspection_q5a.py](C:/AiUE/workflows/pmx_pipeline/run_visible_conflict_inspection_q5a.py)
  - [run_visible_conflict_inspection_q5a.ps1](C:/AiUE/run_visible_conflict_inspection_q5a.ps1)
- regression coverage:
  - [test_q5a_visible_conflict.py](C:/AiUE/tests/t1/test_q5a_visible_conflict.py)

## Important Design Decision

`Q5A` still uses a dedicated QA capture path, but the stable implementation is now more pragmatic than the first draft.

The current passing lane uses:

- hard-coded green/red QA materials in the shared plugin
- dominance-aware color thresholding in the Python analyzer

This means the analyzer no longer requires ideal `255/0/0` or `0/255/0` pixels.  
It accepts the tonemapped but still clearly color-dominant masks produced by the current UE render path.

The dedicated `body_only / slot_only / combined_visible` QA passes are still the source of truth.  
It is **not** using ordinary final-color screenshots.

To keep capture quality visible instead of hiding it behind a green gate, the report records:

- top-level `mask_capture_signal`
- per-shot `mask_extraction_mode`
- per-shot `mask_extraction_signal`

In the current latest passing report, all `4/4` shot sets use `color_threshold`.

## Attach Hardening That Unblocked Q5A

One ready bundle was previously resolving the clothing fixture to a weak generic anchor and could not pass `Q5A` consistently.

The key runtime hardening landed in:

- [PMXCharacterEquipmentComponent.cpp](C:/AiUE/tools/unreal_plugins/AiUEPmxRuntime/Source/AiUEPmxRuntime/Private/PMXCharacterEquipmentComponent.cpp)

What changed:

- wearable fallback bone scoring now includes a spatial preference for upper-body / head-adjacent bones
- this lets badly named PMX rigs recover to a stronger attachment than `owner_origin`

Current resolved clothing attach states in the passing `Q5A` report:

- `mingchao_sample_c0aeb7ff_character_35215ba5`
  - `resolved_attach_socket_name = Bone_160`
  - `attach_resolution_mode = fallback_bone_score`
- `mingchao_xjqy8yn4h6_b6e33424_character_f91ab5d6`
  - `resolved_attach_socket_name = Bone_Ctr_B_HairB_01_091`
  - `attach_resolution_mode = fallback_bone_pattern`

## Tooling Integration

`Q5A` is now visible in the tooling layer:

- `T1` latest evidence pack includes the raw pass images and debug overlays
  - [manifest.json](C:/AiUE/Saved/tooling/t1/latest/manifest.json)
- `T2` native workbench reads `visible_conflict_inspection_q5a` under `platform_line`

## Related Regression

After the final `Q5A` pass, these still pass:

- [latest_clothing_vertical_slice_p2_report.json](C:/AiUE/Saved/verification/latest_clothing_vertical_slice_p2_report.json)
- [latest_multi_slot_quality_gate_q4_report.json](C:/AiUE/Saved/verification/latest_multi_slot_quality_gate_q4_report.json)
- [latest_visible_conflict_inspection_q5a_report.json](C:/AiUE/Saved/verification/latest_visible_conflict_inspection_q5a_report.json)

And the native tooling smoke still passes through:

- [manifest.json](C:/AiUE/Saved/tooling/t1/latest/manifest.json)

## Residual Debt

`Q5A v1` is useful and passing, but it is not the final shape.

Open follow-ups:

- decide whether to push further toward truer `0/255` pure-color masks, or accept the current dominance-aware color path as the stable contract
- expand from `body vs clothing` to later `weapon` and `fx` cases
- add volumetric / fit inspection as the next heavier QA layer
- decide whether a stronger fixed-stage capture lane is needed specifically for QA

## Next Step

The most natural next quality step is:

- `Q5B`: volumetric or fit-aware inspection

The smaller hardening step that was previously open is now substantially complete:

- `Q5A.x`: the gate no longer needs silhouette fallback on the current machine
