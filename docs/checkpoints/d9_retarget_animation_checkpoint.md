# D9 Retarget Animation Checkpoint

## Scope

This checkpoint captures the `D3 -> D9` demo-animation stack:

- `D3`: first real animation preview attempt on demo host
- `D4`: retarget preflight
- `D5`: source IK rig / retarget bootstrap
- `D6`: source retarget chain authoring
- `D7`: chain refinement and exact-name mapping
- `D8`: first passing retargeted animation preview
- `D9`: small multi-animation matrix on the same PMX character

The intent of this stack is to prove that AiUE can move beyond static visibility checks and produce repeatable motion evidence on imported PMX content inside `AiUEdemo`.

## Main Outcome

This stack establishes a working preview path for retargeted demo animations:

- a PMX character can resolve into a demo-host preview target
- mannequin demo animations can be retargeted onto the PMX skeleton
- native runtime pose evaluation can prove bone motion on the host side
- before/after screenshots can be compared with cropped external motion evidence
- the same retarget path now passes for a small matrix of real animation assets

The latest passing reports are:

- `D8`: `Saved/verification/latest_demo_retargeted_animation_preview_d8_report.json`
- `D9`: `Saved/verification/latest_demo_animation_matrix_d9_report.json`

## Key Design Decisions

- Keep `UEIntroProject` as the kernel host and `AiUEdemo` as the demo host.
- Do not depend on Python-only animation sampling APIs for final motion proof.
- Use shared plugin native pose evaluation as the authoritative engine-side animation signal.
- Use cropped image-delta evidence as the first external proof layer.
- Keep `G2` history out of this checkpoint; `D3 -> D9` is now the active demo-animation line.

## What Passed

- `D4`: retarget tooling availability and asset readiness checks
- `D5`: source IK rig and retargeter bootstrap
- `D7`: meaningful source chain coverage and exact-named mappings
- `D8`: first passing retargeted animation preview for one real animation
- `D9`: passing multi-animation matrix for:
  - `MM_Attack_01`
  - `MM_Attack_02`
  - `MM_Attack_03`

## Current Limits

- The current proof focuses on a single ready PMX character bundle.
- External proof is still motion-oriented, not semantic pose QA.
- The animation set is intentionally small and controlled.

## Recommended Next Step

`D10` should stay narrow:

- keep using `AiUEdemo`
- reuse the same ready PMX bundle first
- add a small mixed set such as `idle + attack + locomotion`
- verify that retarget preview remains stable across more than one motion family

This is a better next step than broad cleanup or texture work because the highest-value risk is still animation credibility, not import breadth.
