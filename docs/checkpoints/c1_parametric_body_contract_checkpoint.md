# C1 Parametric Body Contract Checkpoint

## Goal

`C1` stands directly on top of `C0`.

It does not solve fusion, rigging, or runtime body assembly.
It fixes a narrower but critical problem:

`Which body combinations are actually legal in the first narrow-domain body family, and which module IDs define that contract?`

## Fixed Inputs

- `latest_modular_morphology_inventory_c0_report.json`
- the canonical fixture family selected by `C0`

## Fixed Output

`C1` writes:

- `parametric_body_contract_report.json`
- `parametric_body_contract_latest.json`
- `latest_parametric_body_contract_c1_report.json`

The report must carry:

- `body_family_id`
- `contract_id`
- `core_module_id`
- `supported_head_ids`
- `supported_bust_classes`
- `supported_leg_length_profiles`
- `compatible_hair_ids`
- `fusion_recipe_id`
- `rig_profile_id`
- `material_profile_id`

## First-Pass Rules

`C1` is intentionally narrow and static.

First-pass policy is:

- `head` is a required discrete axis
- `bust` is a required discrete axis
- `leg_length` is a required discrete axis
- `hair` is an optional compatibility axis
- `core_torso_arm` is fixed

`C1` passes only when the selected canonical family has:

- at least one head
- at least one bust variant
- at least one leg profile
- exactly one fixed core path chosen for the contract

`C1` does not yet attempt:

- generic humanoid abstraction
- runtime raw-fragment swapping
- procedural legality rules across multiple families

## Why This Node Exists

Without `C1`, the next nodes would still have to guess:

- which module IDs define the supported body family
- whether hair belongs inside the body contract core
- how to name the fusion, rig, and material profiles

With `C1`, the repo gains a stable first contract for:

- `C2 Canonical Fusion Fixture`
- `C3 Skeletal Transfer Proof`
- `T1/T2` body-platform state

## Next Node

If `C1` is green and the contract looks believable, the next implementation node is:

- `C2 Canonical Fusion Fixture`
