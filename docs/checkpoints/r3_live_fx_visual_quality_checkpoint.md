# R3 Live FX Visual Quality Checkpoint

## Summary

`R3` upgrades the FX line from `runtime-valid Niagara slot` to `same-session live-pixel evidence`.

Unlike `R2`, this gate does not stop at:

- `NiagaraComponent` creation
- resolved attach state
- non-zero fixed bounds

It now asks a stronger question:

- does the screenshot with FX differ measurably from the screenshot without FX, on the same host, in the same editor session, in the same shot?

## What R3 Measures

For each ready bundle, `R3` now captures a same-session visual pair:

- baseline: no `fx` override
- with-fx: same spawned host + same level + same shot ids + Niagara slot override

It then compares:

- `front`
- `side`

using two evidence windows:

- full-frame image delta
- FX-cropped image delta derived from `tracked_slot_coverages.fx.screen_rect`

## Current Outcome

Latest report:

- `Saved/verification/latest_live_fx_visual_quality_r3_report.json`

Current status:

- `pass`

Current execution profile:

- `scene_capture_source = SCS_FINAL_COLOR_HDR`
- `scene_capture_warmup_count = 4`
- `scene_capture_warmup_delay_seconds = 0.08`
- `niagara_desired_age_seconds = 0.08`

Current proof:

- both ready bundles pass
- `front` and `side` strict shots both produce measurable baseline-vs-with-fx pixel delta
- the with-fx result preserves the expected `DirectionalBurst` Niagara asset on the managed `fx` slot

## Why This Matters

Without `R3`, the platform could still over-credit FX quality based only on:

- attach success
- asset identity
- fixed bounds

`R3` closes that gap by requiring live rendered delta, not just attach success.

## Decision

`R3.1` is now complete:

- the gate no longer compares baseline and with-fx across separate host sessions
- it captures both states against the same spawned host inside the same editor session
- the editor capture path is now hardened around `SCS_FINAL_COLOR_HDR` plus warmup

Recommended next priority after this checkpoint:

- expand FX quality from `pixel delta exists` to stronger `FX prominence / semantic readability`
