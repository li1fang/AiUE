# Governance

## Model

`AiUE` uses `Core ADR, Workflow Light`.

- Core changes require an ADR or mini-RFC
- Workflow and lab changes can move faster as long as they do not change stable CLI or schema surfaces
- Breaking stable-surface changes require explicit design review before implementation

## Roles

- Maintainers: own release decisions, stable surface, and governance enforcement
- Reviewers: review routed changes within their lane
- Contributors: propose changes through issues, discussions, ADRs, or pull requests

## Lane Routing

Every change must identify a primary lane:

- `Core`
- `Workflow`
- `Labs`
- `Reliability`
- `Repo Hygiene`
- `Data Contract`

Cross-lane changes must explicitly call out the stable-surface risk.

## Decision Rules

- Stable CLI/schema changes: review required before implementation
- Workflow/lab iteration that does not touch stable surface: lighter design path allowed
- Safety boundary changes: maintainer review required
- Release gate changes: maintainer review required

## Public Alpha Rule

Public Alpha favors collaborative development over feature breadth.

If there is a conflict, protect:

- stable surface
- release gates
- destructive safety boundaries
- compatibility documentation
