# C0 Modular Morphology Inventory Checkpoint

## Goal

`C0` is the first executable node of the new `Body Platform Line`.

It does not implement runtime modular assembly.
It answers a narrower and more useful question:

`What modular body source modules do we actually have, how do they cluster into families, and which family is strong enough to serve as the first canonical body-platform fixture?`

## Fixed Inputs

- local workspace config
- `paths.body_morphology_source_root`
  - legacy alias: `paths.parametric_body_source_root`

## Fixed Output

`C0` writes:

- `modular_morphology_inventory_report.json`
- `modular_morphology_inventory_latest.json`
- `latest_modular_morphology_inventory_c0_report.json`

The report is expected to provide:

- source-root evidence
- module-kind counts
- family-level grouping
- candidate fixture families
- canonical fixture-family selection

## First-Pass Rules

The current `C0` heuristics are intentionally lightweight.

They classify discovered mesh modules into:

- `head`
- `hair`
- `bust_variant`
- `core_torso_arm`
- `leg_profile`
- `non_consumable_raw_scan`
- `unknown`

`C0` passes only when it can find at least one family containing:

- `head`
- `bust_variant`
- `leg_profile`
- `core_torso_arm`

`hair` is optional in `C0`.

## Why This Node Exists

Without `C0`, the body-platform discussion will drift into:

- vague runtime hopes
- unscoped modularity claims
- contract guesses that are not grounded in the actual source geometry

With `C0`, the repo gains a machine-readable starting point for:

- `C1 Parametric Body Contract`
- `C2 Canonical Fusion Fixture`
- `T1/T2` body-platform evidence

## Next Node

If `C0` is green and the canonical family looks believable, the next implementation node is:

- `C1 Parametric Body Contract`
