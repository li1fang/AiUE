# T1 Metrics + Tooling Foundation Checkpoint

## Summary

`T1` completes the first dedicated tooling phase after the slot platform and quality lines.

It does not add a new content gate. Instead, it stabilizes the layer underneath:

- Python-based image metrics
- repo-managed tooling environment
- static HTML evidence pack
- slot/attach evidence normalization
- pytest coverage for pure Python evaluation logic

## What Landed

- repo-managed tooling env bootstrap:
  - `tools/bootstrap_t1_tooling.ps1`
  - fixed default interpreter: `python3.12.exe`
  - virtual environment: `C:\AiUE\.venv-tooling`
- upgraded image comparison entry:
  - `tools/compare_image_motion.ps1`
  - Python-first, legacy PowerShell fallback
  - added `engine`, `mask_path`, `effective_pixel_count`, `mask_pixel_count`, `mask_ratio`, `ssim`
- new Python tooling modules:
  - image metrics
  - latest-report indexing
  - slot debugger normalization
  - static evidence pack generation
- static evidence pack entry:
  - `tools/run_t1_evidence_pack.ps1`
  - output root: `Saved/tooling/t1/<run_stamp>/`
  - latest pointer: `Saved/tooling/t1/latest/`
- pytest coverage for:
  - image metrics
  - report indexing
  - slot debugger normalization
  - evidence pack manifest generation

## Verification

The following were verified during `T1`:

- `pytest` passes in `.venv-tooling`
- `tools/compare_image_motion.ps1` resolves to the Python engine when `.venv-tooling` is present
- `tools/run_t1_evidence_pack.ps1` produces a static HTML pack under `Saved/tooling/t1/latest/`
- targeted regressions still pass:
  - `D12`
  - `Q4`
  - `R3`

Current latest reports still passing:

- `Saved/verification/latest_demo_cross_bundle_regression_d12_report.json`
- `Saved/verification/latest_multi_slot_quality_gate_q4_report.json`
- `Saved/verification/latest_live_fx_visual_quality_r3_report.json`

## Notes

- The Python metrics path now uses a compatibility-oriented resize path so that `R3` keeps passing on the same thresholds that were previously tuned around the legacy image comparison behavior.
- `mask` support is present at the metrics layer, but `Q5A` mask/depth capture is still future work.
- `external_candidate_sources` placeholders are now present in the report index and slot debugger payloads for future `A1` integration.
