# Q5B Volumetric Fit Inspection Checkpoint

## Summary

`Q5B` is the first fit-aware quality gate on top of `Q5A`.

Its current scope is intentionally narrow:

- host: `demo`
- slot under inspection: `clothing`
- fixture: `SKM_Echo_Hair`
- prerequisite: passing `Q5A` with `color_threshold` mask extraction on every shot

The goal of `Q5B v1` is not full voxel collision analysis yet.

The goal is to prove that AiUE can run a deterministic spatial-fit loop using the evidence we already have:

- read the latest passing `Q5A` report
- reuse the per-package host result artifacts emitted by `Q5A`
- evaluate clothing fit using attach anchor + bounds heuristics
- write a gate-style report
- surface the result through `T1` and `T2`

## Passing Evidence

The current passing report is:

- [latest_volumetric_fit_inspection_q5b_report.json](C:/AiUE/Saved/verification/latest_volumetric_fit_inspection_q5b_report.json)

Current passing outcome:

- `status = pass`
- `required_package_count = 2`
- `resolved_package_count = 2`
- `packages = 2`
- `passing_packages = 2`
- `color_threshold_source_packages = 2`

The first full-pass discussion signal is present:

- `discussion_signal.reason = first_complete_q5b_pass`

## What Landed

The main pieces are:

- fit analysis:
  - [q5b_volumetric_fit.py](C:/AiUE/tools/t1/python/aiue_t1/q5b_volumetric_fit.py)
- gate runner:
  - [run_volumetric_fit_inspection_q5b.py](C:/AiUE/workflows/pmx_pipeline/run_volumetric_fit_inspection_q5b.py)
  - [run_volumetric_fit_inspection_q5b.ps1](C:/AiUE/run_volumetric_fit_inspection_q5b.ps1)
- regression coverage:
  - [test_q5b_volumetric_fit.py](C:/AiUE/tests/t1/test_q5b_volumetric_fit.py)
- tooling classification:
  - [report_index.py](C:/AiUE/tools/t1/python/aiue_t1/report_index.py)

## Important Design Decision

`Q5B v1` is deliberately **fit-aware**, not fully voxelized.

It does **not** claim to compute triangle-level or voxel-level physical penetration.
That heavier layer is still a later step.

The current gate stands on these inputs from the `Q5A` host result:

- `body_component.bounds`
- `slot_component.bounds`
- `slot_component.attach.world_transform.location`
- `clothing_attach_state`
- `Q5A` supporting shot metrics and mask modes

From that, `Q5B v1` evaluates a narrow but useful set of heuristics:

- anchor vertical placement relative to body bounds
- anchor lateral placement relative to body bounds
- anchor surface gap near the body top band
- slot min-height offset above the resolved anchor

This is honest about the current evidence quality, and it is already useful for catching:

- obvious floating / detached placement
- anchors that drift too far outside the intended body region
- fixture offsets that no longer match the expected mounted pose

## Current Stable Contract

The fixed thresholds are:

- `anchor_vertical_ratio_min = 0.85`
- `anchor_vertical_ratio_max = 1.05`
- `anchor_lateral_ratio_max = 1.05`
- `anchor_surface_gap_z_min = -20.0`
- `anchor_surface_gap_z_max = 10.0`
- `slot_min_above_anchor_ratio_min = 5.0`
- `slot_min_above_anchor_ratio_max = 7.0`

These thresholds are intentionally calibrated to the current fixed hair fixture, not to arbitrary future clothing assets.

## Tooling Integration

`Q5B` now appears in the tooling layer:

- `T1` report index classifies `volumetric_fit_inspection_q5b` under `platform_line`
  - [manifest.json](C:/AiUE/Saved/tooling/t1/latest/manifest.json)
- `T2` native workbench can read the latest `Q5B` report from the same latest manifest

## Residual Debt

`Q5B v1` is a real quality step, but it is not the final physical-inspection layer.

Open follow-ups:

- move from bounds-and-anchor heuristics toward local volumetric overlap or signed-distance style evidence
- decide whether host-side capture should emit richer spatial artifacts for `Q5B.x`
- expand beyond the fixed hair fixture into broader clothing categories
- later extend the same idea to weapon / FX coexistence

## Next Step

The most natural next quality step is:

- `Q5B.x`: richer spatial evidence for the same clothing fixture

After that, the heavier path is:

- `Q5C`: true volumetric or embedding-rate inspection
