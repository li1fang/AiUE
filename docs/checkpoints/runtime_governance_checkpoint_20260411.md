# Runtime Governance Checkpoint (2026-04-11)

## Summary

This checkpoint records the current governance state of the shared Unreal runtime.
It does not introduce a new content capability. It documents the refactor progress,
the remaining hotspots, and the current regression evidence after the recent
capture, inspection, preview, and retarget split work.

The active line remains:

- `V1 -> D1 -> D12 -> Q1 -> Q2 -> Q3`
- `P1 -> P2 -> R2 -> R3`
- `Q5A -> Q5B -> Q5B.x -> E1 -> Q5C-lite`

The immediate goal of this checkpoint is simple:

- keep the command surface stable
- keep the latest report names stable
- confirm that the runtime is now mostly organized as thin shims plus focused modules
- stop before entering `common.py`

## Current Structure

| Module | Lines | Role |
| --- | ---: | --- |
| `capture.py` | 21 | Export surface only; `capture_frame` and `run_scene_sweep` moved out. |
| `composition.py` | 10 | Export surface only; import and registry commands now live in dedicated modules. |
| `composition_registry.py` | 33 | Export surface only; asset helpers and slot/runtime helpers now live in dedicated modules. |
| `inspection.py` | 16 | Export surface only; implementation moved into focused helpers. |
| `inspection_inventory.py` | 12 | Compatibility shim for inventory style inspection entry points. |
| `preview.py` | 12 | Export surface only; preview implementation is split out. |
| `retarget.py` | 12 | Export surface only; retarget implementation is split out. |

## Remaining Hotspots

| Module | Lines | Current Read |
| --- | ---: | --- |
| `common.py` | 2237 | Biggest hotspot. Do not split next without a clear forcing function. |
| `retarget_preview.py` | 1180 | Large, but now isolated behind a thin retarget shim. |
| `retarget_profile.py` | 1078 | Large, but now isolated behind a thin retarget shim. |
| `composition_registry_bindings.py` | 326 | Bounded slot/runtime helper layer; safer next candidate than `common.py`. |
| `composition_import.py` | 249 | Still helper-heavy, but no longer shares a command shim with registry creation. |
| `composition_registry_assets.py` | 133 | Asset/path helper layer; acceptable size after split. |
| `capture_visual.py` | 383 | Acceptable for now; not the next pressure point. |

## Governance Progress

Recent governance slices now in the branch:

- `refactor(unreal): split q5a inspection helpers`
- `refactor(unreal): share inspection host session helpers`
- `refactor(unreal): split visual inspection capture helpers`
- `refactor(unreal): split visual inspection state and shots`
- `refactor(unreal): split q5a inspection state and pass helpers`
- `refactor(unreal): split inventory inspection probes`
- `refactor(unreal): split capture command shims`
- `refactor(unreal): share retarget host session helpers`
- `refactor(unreal): split retarget author chains command`
- `refactor(unreal): split retarget preflight and bootstrap commands`
- `refactor(unreal): split composition command shims`
- `refactor(unreal): split composition registry helpers`

Net effect:

- capture, inspection, preview, and retarget are no longer concentrated in a single large dispatcher file
- the command names and request/response contracts remain stable
- the new module boundaries are implementation-oriented rather than feature-branch experiments

## Verification State

Latest reports currently read as `pass`:

| Report | Status |
| --- | --- |
| `latest_visual_proof_v1_report.json` | `pass` |
| `latest_demo_stage_d1_onboarding_report.json` | `pass` |
| `latest_demo_cross_bundle_regression_d12_report.json` | `pass` |
| `latest_demo_shot_quality_gate_q1_report.json` | `pass` |
| `latest_demo_composition_quality_gate_q2_report.json` | `pass` |
| `latest_demo_semantic_framing_gate_q3_report.json` | `pass` |
| `latest_generic_slot_abstraction_p1_report.json` | `pass` |
| `latest_clothing_vertical_slice_p2_report.json` | `pass` |
| `latest_real_fx_item_kind_r2_report.json` | `pass` |
| `latest_live_fx_visual_quality_r3_report.json` | `pass` |
| `latest_visible_conflict_inspection_q5a_report.json` | `pass` |
| `latest_volumetric_fit_inspection_q5b_report.json` | `pass` |
| `latest_volumetric_fit_spatial_evidence_q5bx_report.json` | `pass` |
| `latest_showcase_demo_e1_report.json` | `pass` |
| `latest_volumetric_inspection_q5c_lite_report.json` | `pass` |

Targeted regression reruns during this refactor phase also stayed green:

- `P1`
- `V1`
- `D1`
- `G1`
- `D4`
- `D5`
- `D6`
- `D8`

## Decision

1. The runtime is now in a good intermediate state: thin shims plus focused implementation modules for the major command surfaces.
2. `common.py` should not be the next refactor target.
3. `composition.py` and `composition_registry.py` are now both reduced to thin shims; if governance continues, `composition_registry_bindings.py` is the next low-risk bounded candidate.
4. It is also reasonable to stop governance here and return to feature work, because the current structure is already materially better than the previous single-file concentration.

## Recommended Next Step

Treat this checkpoint as a deliberate stop point.

The next move should be one of:

1. Continue governance with `composition_registry_bindings.py` as the next bounded target.
2. Pause governance and review whether the runtime is stable enough to shift effort back to feature work.

The one move we should avoid next is entering `common.py` without a stronger reason.
