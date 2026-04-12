# ADR-0010: toy-yard Export As The Default PMX Source

## Status

Accepted

## Context

AiUE has now completed the `T1.6 Durable Roundtrip Confirmation` cycle.

What is now true:

- toy-yard portable PMX export is callable from AiUE without falling back to raw `3dgirls` package discovery
- solo `import-package + validate-package` succeeds against toy-yard export packets
- bundle import and attach semantics succeed against toy-yard export packets
- durable runtime roundtrip now repopulates runtime mesh evidence into the re-exported registry
- the remaining runtime preview defect was resolved on the AiUE side rather than by changing the toy-yard contract shape again

This changes the strategic question.

The question is no longer:

- can toy-yard be used as an alternate PMX source for trial packets

The new question is:

- how should AiUE promote toy-yard export into the default PMX source for new runs without losing debuggability or widening scope too abruptly

## Decision

AiUE adopts `toy-yard export` as the default PMX source for new runs.

This decision is implemented as a narrow rollout, not as a repo-wide flag day.

### Rollout Rules

The default-source route is fixed as:

1. workspace configs may declare `paths.toy_yard_pmx_view_root`
2. when that root is present and valid, AiUE should prefer:
   - `summary/ue_equipment_assets_report*.json`
   - `summary/ue_suite_summary.json`
   - `summary/ue_equipment_registry.json`
3. when the toy-yard root is absent, AiUE continues to fall back to existing local conversion and auto-UE outputs
4. raw `3dgirls` remains historical lineage input, not the default package-discovery source for new runs

### Boundary

This ADR changes default PMX source resolution.

It does **not**:

- replace toy-yard as the authority for canonical warehouse data
- change the stable `aiue.ps1` surface
- require all historical workspaces to switch immediately
- make motion part of the PMX default-source rollout

## Consequences

Positive:

- new runs can use a portable export packet as the normal starting point
- AiUE can reason from summary/registry/manifests that are already shaped for downstream consumption
- the package-discovery path becomes more deterministic and less coupled to legacy local layouts
- the boundary between warehouse concerns and runtime concerns stays clearer

Tradeoffs:

- AiUE now depends more heavily on the toy-yard export packet being internally consistent
- summary/registry/manifests become even more important diagnostic surfaces
- the repo must keep fallback behavior honest so old workspaces do not break unexpectedly

## Follow-Up

The first implementation slice for this ADR is:

- add a formal toy-yard view resolution layer in `workflows/pmx_pipeline`
- make the current PMX gates prefer toy-yard summary/registry/report inputs when configured
- document the route as a checkpoint before widening it further

After that, the next target becomes:

- `T2`: run a real new PMX workflow using toy-yard export as the default source without raw `3dgirls` package discovery
