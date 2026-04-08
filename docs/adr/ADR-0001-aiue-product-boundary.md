# ADR-0001: AiUE Product Boundary

## Status

Accepted

## Decision

`AiUE` is the platform. `PMXPipeline` is the first workflow pack.

## Why

- platform logic already extends beyond one import scenario
- capability, guard, policy, and schema systems are reusable
- the project is preparing for public collaborative development

## Consequences

- monorepo stays intact
- workflow packs stay under `workflows/`
- platform docs and governance live at repo root
