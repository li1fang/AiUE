# R1 Clothing Attach Hardening Checkpoint

## Summary

`R1` hardened the shared wearable attach heuristics so the current two ready bundles no longer rely on `owner_origin` for the `clothing` slot.

This work stayed inside the existing shared runtime and quality line:

- broaden wearable token recognition for head / hair / face style bones
- add a generic PMX central-bone fallback path for wearable slots
- keep the earliest best-scoring fallback bone instead of drifting to the last equally scored bone
- remove `Q4` tolerance for `owner_origin` clothing fallback

## Key Runtime Change

The core hardening landed in:

- `tools/unreal_plugins/AiUEPmxRuntime/Source/AiUEPmxRuntime/Private/PMXCharacterEquipmentComponent.cpp`

What changed:

- wearable pattern matching now recognizes more head-adjacent names such as `haira`, `hairb`, `face`, `kao`, `ear`, `mimi`, `brow`, `eye`, and `collar`
- wearable scoring now prefers generic central PMX bones when the skeleton exposes mostly numbered `Bone_*` names
- equal fallback scores now keep the earlier candidate, which is more stable for numbered PMX rigs

## Validation

Latest passing reports:

- `P2`: `Saved/verification/latest_clothing_vertical_slice_p2_report.json`
- `P4`: `Saved/verification/latest_multi_slot_composition_p4_report.json`
- `Q4`: `Saved/verification/latest_multi_slot_quality_gate_q4_report.json`

Current outcome:

- `mingchao_sample_c0aeb7ff_character_35215ba5`
  - clothing attach mode: `fallback_bone_score`
  - resolved target: `Bone_160`
- `mingchao_xjqy8yn4h6_b6e33424_character_f91ab5d6`
  - clothing attach mode: `fallback_bone_pattern`
  - resolved target: `Bone_Ctr_B_HairB_01_091`

Most important gate result:

- `Q4` still passes
- `packages_using_clothing_owner_origin_fallback = 0`
- `allow_clothing_owner_origin_fallback = false`

## Residual Risk

`R1` removed the soft fallback, but one package still resolves clothing through a generic PMX fallback bone:

- `Bone_160`

That is much better than `owner_origin`, but it is not yet as semantically strong as a true head / hair / hat socket or bone.

So the remaining risk is now narrower:

- no longer "clothing may float from actor origin"
- now "some clothing may attach to a generic upper-body PMX anchor rather than a semantically named head bone"

## Decision

`R1` is complete enough to unblock the next platform step.

Recommended next phase:

- `R2`: real FX item kind
