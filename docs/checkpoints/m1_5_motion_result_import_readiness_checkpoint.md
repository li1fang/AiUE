# M1.5 Motion Result Import Readiness Checkpoint

## Summary

`M1.5` stands directly on top of `M1`.

`M1` answered:

- can the controlled motion baseline rerun and stay credible

`M1.5` answers a different question:

- are those motion consumer results ready to flow back into toy-yard without manual guesswork

This node is intentionally lighter than `M1`.

It does not rerun Unreal.

It audits the result set already produced by `M1` and checks whether the paths, identities, artifacts, and ownership signals are stable enough for result import.

## Fixed Focus

`M1.5` reads:

- `latest_motion_consumer_baseline_m1_report.json`

And verifies, for each iteration:

- `motion_consumer_result_v0` shape is present
- `packet_manifest_path` exists
- `package_id` and `sample_id` do not drift
- `owner = none`
- `should_contact_toy_yard = false`
- preview evidence artifacts exist
- import/preview action json exists
- `motion_import_report.local.json` exists
- `motion_preview_report.local.json` exists

## Pass Meaning

If `M1.5` passes, AiUE has not only a stable motion execution baseline, but also a stable result-import surface.

That means the next toy-yard coordination step can be based on:

- a repeatable baseline
- machine-readable ownership routing
- a concrete artifact list that can be imported without manual hunting

## Why This Node Matters

This checkpoint reduces a common integration trap:

- execution looks green inside AiUE
- but the counterparty still cannot reliably consume the result

`M1.5` is the bridge that makes the baseline operational for cross-repo roundtrip, not just locally impressive.
