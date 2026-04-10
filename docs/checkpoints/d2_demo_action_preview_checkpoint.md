# D2 Demo Action Preview Checkpoint

## Node Name
`Checkpoint B: D2 demo action preview pass`

## Why This Node Exists
This node marks the first point where the demo host can prove not only that a character package is visible, but also that a controlled action request changes the rendered result in a measurable way.

This checkpoint is intentionally narrower than a full animation system. It proves:
- the demo host can spawn a ready character+weapon bundle
- the host can execute a controlled action preview against that spawned actor
- fixed camera captures can be taken before and after the action
- an external image-difference check can confirm that the rendered output changed

It does **not** yet prove:
- imported characters can play production animation assets
- skeleton retargeting is wired for arbitrary incoming models
- action semantics are correct beyond "the rendered pose/frame changed"

## Entry Criteria
Before using this node, these should all be true:
- `run_visual_proof_v1.ps1` passes on the kernel host
- `run_demo_gate_d1.ps1` passes on the demo host
- `run_demo_action_preview_d2.ps1` produces a passing report

## What This Commit Should Include
- demo-host `action-preview` command support in the shared host bridge/runtime
- the `D2` runner and launcher:
  - `workflows/pmx_pipeline/run_demo_action_preview_d2.py`
  - `run_demo_action_preview_d2.ps1`
- the external motion evidence helper:
  - `tools/compare_image_motion.ps1`
- command surface updates required to route and expose `action-preview`
- documentation that explains the checkpoint boundary

## What Must Stay Out Of The Commit
- `local/`
- `Saved/`
- `deps/`
- generated reports, screenshots, and capture manifests
- historical `G2` fixed-stage experiment files unless they are intentionally revived later

## Scope Statement
`D2` should currently be described as:
- `demo host controlled action preview`
- `engine-side transform evidence`
- `external histogram-based motion evidence`

`D2` should **not** currently be described as:
- `full animation playback`
- `retargeted imported-character animation validation`
- `pose-level action QA`

## Suggested Next Step
After this checkpoint lands, the most practical next goal is:

`D3: demo host real animation preview`

That next node should swap the current controlled root action with one explicit animation source while keeping the same before/after capture and external motion evidence structure.
