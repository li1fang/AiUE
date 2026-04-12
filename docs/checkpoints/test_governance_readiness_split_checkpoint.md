# Test Governance Readiness Split Checkpoint

## Why

`TG1` proved useful, but its first report still mixed two different truths:

- automation checkpoint readiness
- manual playable-demo signoff readiness

That made the repo look less precise than it really was once `M1` turned material proof green while `PV1` was still pending.

## What Changed

- split `checkpoint_readiness` into:
  - `automation_checkpoint_ready`
  - `signoff_checkpoint_ready`
- kept the legacy combined `ready` field for compatibility
- taught `T1/T2` to read and show the split explicitly
- marked `manual_playable_demo_validation` as `manual_signoff` in the coverage ledger

## Result

- automation can be reported as ready without pretending human playable-demo signoff already happened
- governance still stays in `attention` while manual signoff is missing
- the repo now says the sharper truth: automated authority and human signoff are related, but not the same thing
