# E2 Playable Demo Bootstrap Checkpoint

## Summary

This checkpoint records the first concrete `E2` slice after `E1` crossed its stability threshold.

It is intentionally narrow.
The goal is not to claim "playable demo finished".
The goal is to prove that `AiUEdemo` now has a reusable session bootstrap layer with evidence-backed package selection, slot composition, animation preset carry-over, and a minimal full-stack smoke run.

## Passing Evidence

The current passing report is:

- [latest_playable_demo_e2_bootstrap_report.json](C:/AiUE/Saved/verification/latest_playable_demo_e2_bootstrap_report.json)

The current latest session manifest is:

- [playable_demo_e2_session.json](C:/AiUE/Saved/demo/e2/latest/playable_demo_e2_session.json)

Current passing outcome:

- `status = pass`
- `required_package_count = 2`
- `resolved_package_count = 2`
- `session_entries = 2`
- `packages_with_animation_presets = 2`
- `session_smoke_passed_packages = 2`
- `session_smoke_total_packages = 2`
- `discussion_signal.reason = first_complete_playable_demo_e2_bootstrap_pass`

Resolved packages:

- `mingchao_sample_c0aeb7ff_character_35215ba5`
- `mingchao_xjqy8yn4h6_b6e33424_character_f91ab5d6`

## What Landed

- gate runner:
  - [run_playable_demo_e2_bootstrap.py](C:/AiUE/workflows/pmx_pipeline/run_playable_demo_e2_bootstrap.py)
  - [run_playable_demo_e2_bootstrap.ps1](C:/AiUE/run_playable_demo_e2_bootstrap.ps1)
- prerequisite consumption:
  - `E1 stability`
  - `E1`
  - `Q4`
  - `R3`
  - `D8`
  - `D12`
  - `D1`
- session output:
  - normalized package order
  - default package id
  - host blueprint asset
  - slot bindings
  - action presets
  - validated animation presets
  - hero-shot evidence links

## What Was Verified

For each of the `2` resolved packages, the bootstrap runner now verifies:

1. all prerequisite reports are present and passing
2. the package survives cross-report intersection across `E1/Q4/R3/D1`
3. a host blueprint asset is available
4. at least one validated animation preset exists
5. a one-shot full-stack `action-preview` smoke passes in `demo host`
6. the smoke result exposes `weapon`, `clothing`, and `fx` slots together

## Boundary

This checkpoint is deliberately not the whole `E2`.

It does **not** yet provide:

- interactive player controls
- a runtime package switcher UI
- a packaged desktop playable demo
- a new stable CLI surface

What it does provide is the first trustworthy session layer that future interactive demo work can sit on top of.

## Consequence

`AiUEdemo` is no longer only producing gate screenshots.
It now has a reproducible session manifest for the current ready bundles, with enough structure to support the next `E2` slice without re-deriving host, slot, and animation context from scratch each time.
