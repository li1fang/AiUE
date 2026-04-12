# T2A toy-yard Default-Source New-Run Confirmation

## Summary

This checkpoint promotes toy-yard export from a successful trial packet source into a first-class default-source workflow entry for new PMX runs.

The purpose of `T2A` is narrow:

- confirm AiUE can start from `paths.toy_yard_pmx_view_root`
- resolve summary, registry, and manifests without raw `3dgirls` package discovery
- complete one real solo lane and one real bundle lane
- leave a machine-readable signal describing whether any follow-up belongs to AiUE or toy-yard

## Fixed Flow

`T2A` is fixed to run two lanes:

1. `solo`
   - select the first consumer-ready character package from toy-yard summary
   - run `import-package`
   - run `validate-package`

2. `bundle`
   - select the first resolvable ready pair from toy-yard registry
   - run character import
   - run weapon import
   - run `refresh-assets`

The runner consumes toy-yard export as the default source of truth for:

- `summary/ue_suite_summary.json`
- `summary/ue_equipment_registry.json`
- `conversion/*/manifest.json`

## Communication Node

`T2A` introduces a small but explicit communication node:

- `communication_signal.should_contact_toy_yard = true`
  - when packet artifacts or export contract shape are the likely blocker
- `communication_signal.should_contact_toy_yard = false`
  - when failure looks local to AiUE runtime, registry consumption, or preview logic

This prevents future cross-repo discussion from depending on memory or manual log reading.

## Pass Meaning

`T2A` pass means:

- toy-yard export is the effective default PMX source for a new AiUE run
- solo import/validate passes from export-only inputs
- bundle import/refresh passes from export-only inputs
- at least one runtime-ready host is produced in the bundle lane

It does **not** mean:

- demo, motion, or broader diversity are already widened
- roundtrip durability needs to be re-proven every run
- all historical workflows must switch immediately
