# S1 Stabilization Checkpoint

## Goal
`S1` stabilizes the already-validated line without adding new product surface.

This checkpoint is complete when:

- active host/runtime behavior stays compatible
- the Unreal host monolith is split into runtime modules
- active workflow scripts share common gate/demo helpers
- `G2` is archived outside the active path
- the active reports still pass after the refactor

## Structural Changes
Host runtime is now split under:

- [runtime/common.py](C:/AiUE/adapters/unreal/host_project/runtime/common.py)
- [runtime/composition.py](C:/AiUE/adapters/unreal/host_project/runtime/composition.py)
- [runtime/capture.py](C:/AiUE/adapters/unreal/host_project/runtime/capture.py)
- [runtime/retarget.py](C:/AiUE/adapters/unreal/host_project/runtime/retarget.py)
- [runtime/preview.py](C:/AiUE/adapters/unreal/host_project/runtime/preview.py)
- [runtime/inspection.py](C:/AiUE/adapters/unreal/host_project/runtime/inspection.py)

The old entrypoint remains at [aiue_unreal_command.py](C:/AiUE/adapters/unreal/host_project/aiue_unreal_command.py), but it now acts as dispatcher/shim.

Workflow scaffolding is centralized in:

- [\_gate_common.py](C:/AiUE/workflows/pmx_pipeline/_gate_common.py)
- [\_demo_common.py](C:/AiUE/workflows/pmx_pipeline/_demo_common.py)

## Active Line
The active line is formally defined by [ADR-0003](C:/AiUE/docs/adr/ADR-0003-active-line-and-dual-host-stabilization.md):

- `V1`
- `D1`
- `D12`
- `Q1`
- `Q2`
- `Q3`

## Legacy
`G2` has been retired and archived under:

- [legacy/g2/README.md](C:/AiUE/legacy/g2/README.md)

## Fixed Regression Set
`S1` validates the current line by re-running:

1. shared plugin build for `UEIntroProject`
2. shared plugin build for `AiUEdemo`
3. `V1`
4. `D1`
5. `D12`
6. `Q1`
7. `Q2`
8. `Q3`

The latest reports that define success are:

- [latest_visual_proof_v1_report.json](C:/AiUE/Saved/verification/latest_visual_proof_v1_report.json)
- [latest_demo_stage_d1_onboarding_report.json](C:/AiUE/Saved/verification/latest_demo_stage_d1_onboarding_report.json)
- [latest_demo_cross_bundle_regression_d12_report.json](C:/AiUE/Saved/verification/latest_demo_cross_bundle_regression_d12_report.json)
- [latest_demo_shot_quality_gate_q1_report.json](C:/AiUE/Saved/verification/latest_demo_shot_quality_gate_q1_report.json)
- [latest_demo_composition_quality_gate_q2_report.json](C:/AiUE/Saved/verification/latest_demo_composition_quality_gate_q2_report.json)
- [latest_demo_semantic_framing_gate_q3_report.json](C:/AiUE/Saved/verification/latest_demo_semantic_framing_gate_q3_report.json)
