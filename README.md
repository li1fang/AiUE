# AiUE

`AiUE` is an AI-facing Unreal automation and control layer.

It turns Unreal automation primitives into a stable, guarded, JSON-first platform for tools, agents, and workflow packs.

## What AiUE Is

- A capability registry for "present / callable / reliable" Unreal behaviors
- A guarded CLI for AI-safe automation commands
- A stable schema surface for actions, reports, probe data, and policy outputs
- A workflow-pack host
- A policy layer for mode selection and fallback decisions

## What AiUE Is Not

- Not a replacement for Unreal Python, Gauntlet, Remote Control, Commandlets, or Interchange
- Not an unrestricted destructive shell over arbitrary Unreal projects
- Not a PMX-only tool, even though `PMXPipeline` is the first workflow pack

## Stable Surface

Public Alpha currently freezes these CLI families:

- `aiue probe`
- `aiue run`
- `aiue lab capture`
- `aiue policy recommend-capture`

Public Alpha currently freezes these schema families:

- `aiue_action_spec`
- `aiue_action_result`
- `aiue_capabilities`
- `aiue_probe_report`
- `aiue_capture_lab_report`
- `aiue_capture_policy`

## Product Shape

`AiUE` uses a monorepo with four product layers:

- `core/`: shared schema, policy, registry, and report primitives
- `adapters/`: Unreal-facing command, guard, and execution layers
- `workflows/`: domain workflow packs, currently `pmx_pipeline`
- `labs/`: repeatable experiments, currently `capture`

## Current Status

- Release channel: `Alpha`
- Governance model: `Core ADR, Workflow Light`
- License: `Apache-2.0`
- First official workflow pack: `PMXPipeline`

## Start Here

- [Whitepaper](WHITEPAPER.md)
- [Roadmap](ROADMAP.md)
- [Architecture](docs/aiue_architecture.md)
- [Quickstart](docs/aiue_quickstart.md)
- [Contributing](CONTRIBUTING.md)
- [Governance](GOVERNANCE.md)
- [Release Policy](docs/release_policy.md)
- [Schema Handbook](docs/schema_handbook.md)
