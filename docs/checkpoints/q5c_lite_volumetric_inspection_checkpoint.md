# Q5C-lite Volumetric Inspection Checkpoint

## Summary

`Q5C-lite` is the first deterministic volumetric-style inspection layer in AiUE.

It is intentionally narrow:

- host: `demo`
- slot under inspection: `clothing`
- fixture: `SKM_Echo_Hair`
- packages: current `2` ready bundles

This is not the final self-healing or universal volumetric system.
It is the first stable local-fit inspection layer on top of the richer spatial evidence already introduced by `Q5B.x`.

## Passing Evidence

The current passing report is:

- [latest_volumetric_inspection_q5c_lite_report.json](C:/AiUE/Saved/verification/latest_volumetric_inspection_q5c_lite_report.json)

Current passing outcome:

- `status = pass`
- `required_package_count = 2`
- `resolved_package_count = 2`
- `packages = 2`
- `passing_packages = 2`
- `packages_without_penetration_clusters = 2`
- `discussion_signal.reason = first_complete_q5c_lite_pass`

## What Landed

- local volumetric evaluation:
  - [q5c_lite.py](C:/AiUE/tools/t1/python/aiue_t1/q5c_lite.py)
  - [slot_geometry.py](C:/AiUE/tools/t1/python/aiue_t1/slot_geometry.py)
- gate runner:
  - [run_volumetric_inspection_q5c_lite.py](C:/AiUE/workflows/pmx_pipeline/run_volumetric_inspection_q5c_lite.py)
  - [run_volumetric_inspection_q5c_lite.ps1](C:/AiUE/run_volumetric_inspection_q5c_lite.ps1)
- regression coverage:
  - [test_q5c_lite.py](C:/AiUE/tests/t1/test_q5c_lite.py)

## Output Shape

`Q5C-lite` records:

- `embedding_ratio`
- `floating_ratio`
- `penetration_clusters`
- `local_fit_volume`
- `quality_class`

This keeps the first volumetric layer deterministic and diagnosable without claiming full automatic repair.

## Position In The Quality Line

The quality line is now easier to read:

- `Q5A`: visible conflict
- `Q5B`: fit heuristics
- `Q5B.x`: richer spatial evidence
- `Q5C-lite`: local volumetric inspection

Anything like auto-fix, broader slot coverage, or universal physical correction still belongs to a later `Q5C.x` discussion.
