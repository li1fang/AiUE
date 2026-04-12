# A1 Action Candidate Provider Interface Checkpoint

## Summary

This checkpoint introduces the first real `A1` provider seam.

It adds:

- `run_action_candidate_provider_a1.py`
- `run_action_candidate_provider_a1.ps1`
- `ADR-0009`
- `action_candidate_manifest_v1` schema and example
- T1/T2 consumption for the latest A1 report

## Fixed Scope

`A1` v1 is intentionally narrow.

It currently proves:

- an external provider contract exists
- the contract can resolve the current two ready bundles
- the selected candidate can be consumed through the existing demo session
- the resulting animation preview leaves behind pose-change and external-motion evidence

It does not yet prove:

- arbitrary imported motion assets
- learned-motion generation
- full motion ranking or search

## Main Artifacts

Latest report:

- `Saved/verification/latest_action_candidate_provider_a1_report.json`

Latest provider artifacts:

- `Saved/demo/a1/latest/action_candidate_provider_context.json`
- `Saved/demo/a1/latest/action_candidate_manifest.json`
- `Saved/demo/a1/latest/action_candidate_provider_state.json`

## Verification Intent

The checkpoint is considered healthy when:

- the latest A1 report is `pass`
- both ready bundles resolve
- both selected candidates pass
- T1 evidence pack renders the A1 summary
- T2 summary reads the A1 latest state without regressions
