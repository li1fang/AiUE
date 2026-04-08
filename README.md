# AiUE

`AiUE` is an AI-facing Unreal automation and control layer.

It takes Unreal automation primitives and turns them into a stable, guarded, JSON-first platform that tools, agents, workflow packs, and labs can build on.

## Why AiUE Exists

Unreal already has strong automation building blocks: Python, Commandlets, Gauntlet, Remote Control, and asset pipelines.

What is still missing is a layer that helps agents and automation systems answer questions like:

- Which Unreal behaviors are merely present, and which are actually reliable on this machine and in this mode?
- Which commands are safe to expose to higher-level tools?
- How should a workflow decide between modes, fallbacks, and policies without guessing?
- How can experimental workflow automation grow without destabilizing the platform surface?

`AiUE` is built to answer those questions.

## What AiUE Is

- A capability registry for Unreal behaviors with `present / callable / reliable` semantics
- A guarded CLI and JSON action surface for automation tools and agents
- A stable schema layer for actions, reports, probe data, and policy outputs
- A host for workflow packs such as `PMXPipeline`
- A policy layer for mode selection, fallbacks, and execution recommendations
- A place to run repeatable labs before graduating behavior into the stable platform

## What AiUE Is Not

- Not a replacement for Unreal Python, Gauntlet, Remote Control, Commandlets, or Interchange
- Not an unrestricted destructive shell over arbitrary Unreal projects
- Not a PMX-only tool, even though `PMXPipeline` is the first official workflow pack
- Not a claim that every experimental lab is production-stable

## Stable Alpha Surface

Public Alpha freezes these CLI families:

- `aiue probe`
- `aiue run`
- `aiue lab capture`
- `aiue policy recommend-capture`

Public Alpha freezes these schema families:

- `aiue_action_spec`
- `aiue_action_result`
- `aiue_capabilities`
- `aiue_probe_report`
- `aiue_capture_lab_report`
- `aiue_capture_policy`

Everything else should be treated as evolving implementation detail unless documented otherwise.

## Product Shape

`AiUE` is a monorepo with four product layers:

- `core/`: shared schema, policy, registry, and report primitives
- `adapters/`: Unreal-facing command, guard, and execution layers
- `workflows/`: domain workflow packs, currently `pmx_pipeline`
- `labs/`: repeatable experiments, currently `capture`

## Current Status

- Release channel: `Alpha`
- Governance model: `Core ADR, Workflow Light`
- License: `Apache-2.0`
- First official workflow pack: `PMXPipeline`

## Alpha Guarantees

The current Alpha aims to provide:

- A documented platform boundary
- A stable schema envelope for public JSON artifacts
- Guard rails around destructive commands
- A documented workflow-pack model
- Hard gates for repo surface, schema contracts, bundle audit, and core regression lanes

## Start Here

- [Whitepaper](WHITEPAPER.md)
- [Roadmap](ROADMAP.md)
- [Architecture](docs/aiue_architecture.md)
- [Quickstart](docs/aiue_quickstart.md)
- [Schema Handbook](docs/schema_handbook.md)
- [Release Policy](docs/release_policy.md)
- [Test Lanes and Triplines](docs/test_lanes_and_triplines.md)
- [Contributing](CONTRIBUTING.md)
- [Governance](GOVERNANCE.md)
- [Community Workflow](docs/community_workflow.md)

## Contributing Direction

The public goal is not "more features at any cost". It is "shared development on a stable platform surface".

That means:

- changes to `core` and stable CLI/schema surfaces should go through ADRs or mini-RFCs
- workflow packs can move faster as long as they do not silently mutate the stable surface
- labs are encouraged, but they should graduate into policy or stable commands only after evidence

If you want to contribute a new vertical, the preferred entry point is a workflow-pack proposal rather than adding unrelated logic directly into `PMXPipeline`.
