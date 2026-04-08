# AiUE Architecture

## Repo Shape

```text
AiUE/
  core/
  adapters/
  workflows/
  labs/
  docs/
  schemas/
  examples/
  tools/
```

## Product Layers

### Core

- shared schema contract helpers
- policy derivation
- registry helpers
- report envelope and compatibility primitives

### Adapters

- Unreal command execution
- guard and destructive boundaries
- mode routing
- PowerShell entrypoints

### Workflows

- domain-specific automation packs
- current first official pack: `PMXPipeline`

### Labs

- repeatable experiment systems
- current first lab: `capture`

## Governance Overlay

- `Core ADR, Workflow Light`
- stable-surface changes are slower and documented
- workflow and lab iteration can move faster if they do not redefine stable contracts
