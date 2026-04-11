# E1 Showcase Demo Checkpoint

## Summary

`E1` is the first formal milestone on the demo capability line.

It is intentionally an evidence-first showcase gate, not a playable demo.
Its purpose is to answer one practical question:

- can the current ready bundles be shown credibly inside `AiUEdemo`, with visible character, weapon, clothing, FX, and action change evidence?

## Passing Evidence

The current passing report is:

- [latest_showcase_demo_e1_report.json](C:/AiUE/Saved/verification/latest_showcase_demo_e1_report.json)

Current passing outcome:

- `status = pass`
- `required_package_count = 2`
- `resolved_package_count = 2`
- `packages = 2`
- `passing_packages = 2`
- `captured_before_images = 6`
- `captured_after_images = 6`
- `hero_shots_passed = 2`
- `motion_pass_shots = 6`
- `discussion_signal.reason = first_complete_e1_pass`

## What Landed

- gate runner:
  - [run_showcase_demo_e1.py](C:/AiUE/workflows/pmx_pipeline/run_showcase_demo_e1.py)
  - [run_showcase_demo_e1.ps1](C:/AiUE/run_showcase_demo_e1.ps1)
- host/runtime support:
  - [capture.py](C:/AiUE/adapters/unreal/host_project/runtime/capture.py)
  - [preview.py](C:/AiUE/adapters/unreal/host_project/runtime/preview.py)
  - [_demo_common.py](C:/AiUE/workflows/pmx_pipeline/_demo_common.py)
- tooling integration:
  - [report_index.py](C:/AiUE/tools/t1/python/aiue_t1/report_index.py)
  - [evidence_pack.py](C:/AiUE/tools/t1/python/aiue_t1/evidence_pack.py)

## Important Design Decision

`E1` uses an `action_preview`-backed capture path for the actual evidence shots.

This is deliberate.
`D8/D12` remain prerequisites that prove the validated animation-preview chain exists, but `E1` itself is optimized for deterministic demo evidence rather than for being another retarget-animation gate in disguise.

## Fixed Profile Notes

The current passing profile is:

- host: `demo`
- level: `/Game/Levels/DefaultLevel`
- shots: `front / side / top`
- hero shot: `top`
- action kind: `root_translate_and_turn`
- capture source: `SCS_FINAL_COLOR_HDR`

The hero shot is intentionally `top` in the current passing profile because it is the most reliable frame for showing the full stack without losing the clothing or FX evidence.

## Next Step

`E1` is now a valid showcase checkpoint.
The next demo-line threshold is not "add more demo things" blindly.
It is:

- rerun `E1` until it achieves the required stability condition for entering `E2`
