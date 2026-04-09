# D1 Cleanup And Commit Node

## Node Name
`Checkpoint A: V1 pass + D1 demo onboarding pass`

## Why This Node Exists
This node is the first practical point where the current work can be cleaned up and committed without mixing together too many unfinished goals.

By this node, we expect the repo to contain:
- the shared `AiUEPmxRuntime` plugin source
- dual-host routing and shared host bridge wiring
- `V1` visual proof on the kernel host
- a minimal `D1` demo-host onboarding gate

We do **not** require the full fixed-stage demo gate, advanced action playback, or QA/report-comparison features before this checkpoint.

## Entry Criteria
Before preparing a commit, these should all be true:
- `run_visual_proof_v1.ps1` produces a passing report on the kernel host
- `run_demo_gate_d1.ps1` produces a passing onboarding report on the demo host
- both `UEIntroProjectEditor` and `AiUEdemoEditor` build with the shared plugin installed
- no known regression in `import-package`, `build-equipment-registry`, or `inspect-host`

## What This Commit Should Include
- shared plugin source under `tools/unreal_plugins/AiUEPmxRuntime`
- shared host bridge/runtime scripts under `adapters/unreal/host_project`
- dual-host routing changes in `pipeline_workspace.local.json`
  This file is local-only and should usually stay out of the commit unless we later promote a sanitized example.
- gate runners and launchers:
  - `workflows/pmx_pipeline/run_visual_proof_v1.py`
  - `workflows/pmx_pipeline/run_demo_gate_d1.py`
  - `run_visual_proof_v1.ps1`
  - `run_demo_gate_d1.ps1`
- documentation that explains the checkpoint and current scope

## What Must Stay Out Of The Commit
- `local/`
- `Saved/`
- `deps/`
- generated verification JSON, screenshots, and capture manifests
- generated plugin `Binaries` and `Intermediate`
- host-project generated directories under `UEIntroProject` and `AiUEdemo`

## Cleanup Checklist
- confirm `.gitignore` excludes local datasets, saved verification output, generated plugin build folders, and cloned dependencies
- remove or avoid staging any files under `local/`, `Saved/`, or `deps/`
- confirm new runners only reference committed source paths or local output paths intentionally
- keep commit scope focused on:
  - shared runtime extraction
  - dual-host wiring
  - `V1`
  - minimal `D1`
- postpone larger refactors until after this checkpoint lands

## Suggested Commit Boundary
Use this node once both of these are true:
- `V1` proves the character and weapon are truly visible on the kernel host
- `D1` proves the same ready bundles can be onboarded into `AiUEdemo` and captured there

That gives us a clean story for the commit:
- `kernel host proves visibility`
- `demo host proves onboarding`
- `shared plugin proves the two-host direction is real`
